import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { loadMixamoAnimation } from "./loadMixamoAnimation";
import {
  createSpeakClock,
  MOUTH_SHAPES,
  type MouthShape,
  type SpeakPulseOpts,
} from "./speakClock";

/** VRoid 口型 morph 名（与 preset aa/ih/ou/ee/oh 绑定） */
const SHAPE_TO_MORPH: Record<MouthShape, string> = {
  aa: "Fcl_MTH_A",
  ih: "Fcl_MTH_I",
  ou: "Fcl_MTH_U",
  ee: "Fcl_MTH_E",
  oh: "Fcl_MTH_O",
};

/**
 * 全身取景口型：微放大 + 硬顶；不抬颌。
 * 说话时清掉浅笑相关嘴 morph，避免 Fun/Small 把嘴钉死。
 */
const MOUTH_VISUAL_AMP = 1.22;
/** 单帧口型权重上限 */
const MOUTH_WEIGHT_CAP = 0.55;
/** 与开口抢戏的嘴部 morph（浅笑/抿嘴） */
const MOUTH_CONFLICT_MORPHS = [
  "Fcl_MTH_Fun",
  "Fcl_MTH_Small",
  "Fcl_MTH_Close",
  "Fcl_MTH_Smile",
  "Fcl_MTH_SkinFung",
  "Fcl_MTH_SkinFung_R",
  "Fcl_MTH_SkinFung_L",
] as const;

/** 相对路径：Tauri 安装壳 frontendDist 下绝对 `/…` 偶发贴图协议不一致 */
const MODEL_URL = "./avatars/qi-avatar.vrm";
const IDLE_URL = "./animations/idle.fbx";
const WALK_URL = "./animations/walk.fbx";
/** 去掉头颈动画，避免 VRoid 脸被带出张嘴感 */
const FACE_LOCK_BONES = ["head", "neck", "jaw"];

export type PetLocomotion = "idle" | "walk";
/** 1 = 向屏幕右走，-1 = 向左 */
export type PetFacing = 1 | -1;

/** 与后端 Expression / VRM preset+custom 对齐 */
export type PetFaceExpression =
  | "neutral"
  | "soft_smile"
  | "happy"
  | "quiet"
  | "surprised"
  | "sleepy"
  | "curious";

/** 情绪相关 expression 名（每帧清零后再加目标，避免叠脸） */
const EMOTION_EXPR_NAMES = [
  "happy",
  "angry",
  "sad",
  "relaxed",
  "surprised",
  "neutral",
  "soft_smile",
  "quiet",
  "sleepy",
  "curious",
] as const;

/** 目标权重（边测边调 2026-08-25；2026-09-06 再收 Joy）：
 * - soft_smile 勿混 relaxed（本模型会眯眼）
 * - soft_smile 勿叠 happy/Joy：Joy 眯眼像不屑/鄙视
 * - 浅笑只靠 custom soft_smile（已含轻嘴角 Fun）
 * - happy 以 soft_smile 为主，Joy 极轻
 * - curious 压低，避免皱眉像发愁
 */
const EXPR_TARGETS: Record<PetFaceExpression, Record<string, number>> = {
  neutral: {},
  // 浅笑：只用 custom，不叠 Joy
  soft_smile: { soft_smile: 0.88 },
  happy: { soft_smile: 0.72, happy: 0.12 },
  quiet: { quiet: 0.85 },
  surprised: { surprised: 0.55 },
  sleepy: { sleepy: 1 },
  curious: { curious: 0.38 },
};

export type PetVrmFraming = "pet" | "presence";

export type PetVrmOptions = {
  /** 取景：presence = 单窗相处（全身、朝向你） */
  framing?: PetVrmFraming;
  /** 是否加载 walk（相处页不需要） */
  loadWalk?: boolean;
};

export type PetVrmHandle = {
  ready: Promise<void>;
  destroy: () => void;
  /** 切走相处页时暂停渲染，模型仍常驻内存 */
  setActive: (active: boolean) => void;
  setLocomotion: (mode: PetLocomotion, facing?: PetFacing) => void;
  /** 被点及时：看向你 + 身体微晃（不用 Joy 浅笑，会眯眼像眨眼） */
  notice: (durationMs?: number) => void;
  /** 情绪脸：后端 avatar_state.expression → VRM preset+custom */
  setExpression: (expression: string) => void;
  /**
   * 输出时钟脉冲（今日=文字 delta；日后=TTS 分片接同一入口）。
   * @see ./speakClock.ts
   */
  pulseSpeak: (opts?: SpeakPulseOpts) => void;
  /** 打断/收回：立刻闭嘴 */
  clearSpeak: () => void;
};

/**
 * VRM 渲染：桌宠或单窗相处（idle + 表情 + notice）。
 */
export function createPetVrm(
  container: HTMLElement,
  options: PetVrmOptions = {}
): PetVrmHandle {
  const framing = options.framing ?? "pet";
  const loadWalk = options.loadWalk ?? true;
  let destroyed = false;
  let renderer: THREE.WebGLRenderer | null = null;
  let vrm: VRM | null = null;
  let mixer: THREE.AnimationMixer | null = null;
  let idleAction: THREE.AnimationAction | null = null;
  let walkAction: THREE.AnimationAction | null = null;
  let current: PetLocomotion = "idle";
  let noticeUntil = 0;
  let noticeStart = 0;
  let raf = 0;
  let rendering = true;
  let faceExpr: PetFaceExpression = "neutral";
  /** 当前已应用到模型的权重，向目标缓动 */
  const faceWeights: Record<string, number> = {};
  const speakClock = createSpeakClock();
  /** idle 视线漂移相位（秒） */
  let driftPhase = 0;

  const clock = new THREE.Clock();
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 40);
  /** 视线落点：在脸前方朝向你，避免直接盯相机节点 */
  const lookAtTarget = new THREE.Object3D();
  scene.add(lookAtTarget);
  const _headPos = new THREE.Vector3();
  const _camDir = new THREE.Vector3();
  const _camRight = new THREE.Vector3();
  const _camUp = new THREE.Vector3();

  const key = new THREE.DirectionalLight(0xffffff, 1.2);
  key.position.set(0.45, 1.6, 1.4);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xddeeff, 0.45);
  fill.position.set(-0.8, 0.6, 0.6);
  scene.add(fill);
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));

  let resizeTimer = 0;
  let lastCanvasW = 0;
  let lastCanvasH = 0;
  const presenceFraming = {
    ready: false,
    offsetX: 0,
    cameraY: 0,
    lookY: 0,
    centerZ: 0,
    dist: 0,
    near: 0.05,
    far: 40,
    canvasH: 0,
  };

  const resolvePixelRatio = () => {
    const dpr = window.devicePixelRatio || 1;
    const cap = framing === "presence" ? 2.5 : 2;
    return Math.min(dpr, cap);
  };

  const applyPresenceFraming = (w: number, h: number, force = false) => {
    if (!renderer || !vrm) return;
    const dimChanged =
      Math.abs(w - lastCanvasW) > 2 || Math.abs(h - lastCanvasH) > 2;

    if (presenceFraming.ready && !force && !dimChanged) {
      renderer.setPixelRatio(resolvePixelRatio());
      renderer.setSize(w, h, true);
      camera.aspect = w / h;
      vrm.scene.position.x = presenceFraming.offsetX;
      camera.position.set(
        0,
        presenceFraming.cameraY,
        presenceFraming.centerZ + presenceFraming.dist
      );
      camera.near = presenceFraming.near;
      camera.far = presenceFraming.far;
      camera.lookAt(0, presenceFraming.lookY, presenceFraming.centerZ);
      camera.updateProjectionMatrix();
      return;
    }

    if (!dimChanged && !force) return;

    lastCanvasW = w;
    lastCanvasH = h;
    renderer.setPixelRatio(resolvePixelRatio());
    renderer.setSize(w, h, true);
    camera.aspect = w / h;

    if (presenceFraming.ready && !force) {
      const hRatio = h / (presenceFraming.canvasH || h);
      if (hRatio >= 0.9 && hRatio <= 1.1) {
        vrm.scene.position.x = presenceFraming.offsetX;
        camera.position.set(
          0,
          presenceFraming.cameraY,
          presenceFraming.centerZ + presenceFraming.dist
        );
        camera.near = presenceFraming.near;
        camera.far = presenceFraming.far;
        camera.lookAt(0, presenceFraming.lookY, presenceFraming.centerZ);
        camera.updateProjectionMatrix();
        return;
      }
      presenceFraming.ready = false;
    }

    frameCamera(camera, vrm, framing, presenceFraming);
    presenceFraming.canvasH = h;
    presenceFraming.ready = true;
  };

  const applyResize = () => {
    if (!renderer || destroyed) return;
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    if (framing === "presence") {
      applyPresenceFraming(w, h);
      return;
    }
    const dimChanged =
      Math.abs(w - lastCanvasW) > 2 || Math.abs(h - lastCanvasH) > 2;
    if (!dimChanged) return;
    lastCanvasW = w;
    lastCanvasH = h;
    renderer.setPixelRatio(resolvePixelRatio());
    renderer.setSize(w, h, true);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (vrm) frameCamera(camera, vrm, framing);
  };

  const onResize = () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(applyResize, 100);
  };

  const onWindowResizing = () => {
    window.clearTimeout(resizeTimer);
  };

  const onLayoutSettled = () => {
    window.clearTimeout(resizeTimer);
    applyResize();
  };

  const scheduleTick = () => {
    if (raf || destroyed || !rendering) return;
    raf = requestAnimationFrame(tick);
  };

  const setActive = (active: boolean) => {
    rendering = active;
    if (!active) {
      cancelAnimationFrame(raf);
      raf = 0;
      return;
    }
    clock.getDelta();
    requestAnimationFrame(() => {
      applyResize();
      scheduleTick();
    });
  };

  const tick = () => {
    raf = 0;
    if (destroyed || !renderer || !vrm || !rendering) return;
    const delta = clock.getDelta();
    mixer?.update(delta);
    const mouth = speakClock.tick(delta);
    applyMouthFromClock(vrm, mouth.weights, mouth.active);
    const noticing = clock.elapsedTime < noticeUntil;
    const speakingMouth = mouth.active;
    if (noticing) {
      updateLookAtTarget(0, 0);
      applyNoticeReaction(vrm, clock.elapsedTime, noticeStart, noticeUntil);
      const noticeElapsed = clock.elapsedTime - noticeStart;
      // 回复/点击前半秒盯紧，之后恢复轻眨眼，避免全程瞪眼像紧张
      if (noticeElapsed > 0.35) {
        applyBlink(vrm, clock.elapsedTime);
      } else {
        clearEyeBlink(vrm);
      }
    } else if (speakingMouth) {
      // 说话时轻轻看向你，不做漂移抢戏
      if (vrm.lookAt) vrm.lookAt.target = lookAtTarget;
      updateLookAtTarget(0, 0);
      if (faceExpr === "sleepy") {
        clearEyeBlink(vrm);
      } else {
        applyBlink(vrm, clock.elapsedTime);
      }
    } else {
      // 静默：轻量视线漂移（#2=A）
      driftPhase += delta;
      if (vrm.lookAt) vrm.lookAt.target = lookAtTarget;
      const driftX = Math.sin(driftPhase * 0.35) * 0.08;
      const driftY = Math.sin(driftPhase * 0.22 + 1.2) * 0.03;
      updateLookAtTarget(driftX, driftY);
      if (faceExpr === "sleepy") {
        clearEyeBlink(vrm);
      } else {
        applyBlink(vrm, clock.elapsedTime);
      }
    }
    applyFaceExpression(
      vrm,
      // 说话时暂时卸浅笑/开心，避免 Fun 嘴形钉死开口
      speakingMouth && (faceExpr === "soft_smile" || faceExpr === "happy")
        ? "neutral"
        : faceExpr,
      faceWeights,
      delta
    );
    vrm.update(delta);
    // 全身取景可见性：放大口型 morph（须在 update 之后）
    exaggerateMouthVisibility(vrm, mouth.weights, mouth.active);
    renderer.render(scene, camera);
    scheduleTick();
  };

  const setFacing = (facing: PetFacing, mode: PetLocomotion) => {
    if (!vrm) return;
    // 待机朝向镜头；走路侧身朝行进方向
    if (mode === "idle") {
      vrm.scene.rotation.y = 0;
    } else {
      // 朝向与窗体平移同向（先前符号反了会倒退）
      vrm.scene.rotation.y = facing === 1 ? Math.PI / 2 : -Math.PI / 2;
    }
    frameCamera(camera, vrm, framing);
  };

  const setLocomotion = (mode: PetLocomotion, facing: PetFacing = 1) => {
    if (!mixer || !idleAction) return;
    setFacing(facing, mode);
    if (mode === current && mode === "idle") return;
    if (mode === "walk" && !walkAction) {
      console.warn("[pet] walk 未加载，保持待机");
      return;
    }

    const fade = 0.35;
    const next = mode === "walk" ? walkAction! : idleAction;
    const prev =
      current === "walk" && walkAction ? walkAction : idleAction;

    if (next !== prev) {
      prev.fadeOut(fade);
      next.reset().setEffectiveWeight(1).fadeIn(fade).play();
    } else if (mode === "walk") {
      next.play();
    }
    current = mode;
  };

  const notice = (durationMs = 2600) => {
    if (!vrm) return;
    noticeStart = clock.elapsedTime;
    noticeUntil = noticeStart + durationMs / 1000;
    setLocomotion("idle", 1);
    if (vrm.lookAt) {
      vrm.lookAt.target = lookAtTarget;
    }
  };

  const setExpression = (expression: string) => {
    const key = expression as PetFaceExpression;
    if (key in EXPR_TARGETS) {
      faceExpr = key;
    } else {
      faceExpr = "neutral";
    }
  };

  const pulseSpeak = (opts?: SpeakPulseOpts) => {
    speakClock.pulse(opts);
  };

  const clearSpeak = () => {
    speakClock.clear();
  };

  const updateLookAtTarget = (driftRight = 0, driftUp = 0) => {
    if (!vrm?.lookAt?.target) return;
    const head = vrm.humanoid?.getNormalizedBoneNode("head");
    if (head) {
      head.getWorldPosition(_headPos);
    } else {
      _headPos.set(0, 1.4, 0);
    }
    // 从脸朝相机方向前方一点，像看着你而不是盯镜头内侧
    _camDir.copy(camera.position).sub(_headPos);
    if (_camDir.lengthSq() < 1e-6) _camDir.set(0, 0, 1);
    else _camDir.normalize();
    _camRight.crossVectors(_camDir, camera.up);
    if (_camRight.lengthSq() < 1e-6) _camRight.set(1, 0, 0);
    else _camRight.normalize();
    _camUp.crossVectors(_camRight, _camDir).normalize();
    lookAtTarget.position
      .copy(_headPos)
      .addScaledVector(_camDir, 0.45)
      .addScaledVector(_camRight, driftRight)
      .addScaledVector(_camUp, driftUp);
  };

  const ready = (async () => {
    renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      premultipliedAlpha: false,
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(resolvePixelRatio());
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    window.addEventListener("resize", onResize);
    window.addEventListener("qi-window-resizing", onWindowResizing);
    window.addEventListener("qi-layout-settled", onLayoutSettled);

    const loader = new GLTFLoader();
    // 安装壳 WebView2：ImageBitmapLoader 易出空白贴图（白模）；强制 HTML Image 路径
    loader.register((parser) => {
      const textureLoader = new THREE.TextureLoader(parser.options.manager);
      textureLoader.setCrossOrigin(parser.options.crossOrigin);
      parser.textureLoader = textureLoader;
      return new VRMLoaderPlugin(parser);
    });

    const gltf = await loader.loadAsync(MODEL_URL);
    if (destroyed) return;

    const loaded = gltf.userData.vrm as VRM;
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons(gltf.scene);
    VRMUtils.rotateVRM0(loaded);

    loaded.scene.traverse((obj) => {
      obj.frustumCulled = false;
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const mat of mats) {
        if (!mat) continue;
        const anyMat = mat as THREE.MeshStandardMaterial & {
          map?: THREE.Texture | null;
          needsUpdate?: boolean;
        };
        if (anyMat.map) {
          anyMat.map.colorSpace = THREE.SRGBColorSpace;
          anyMat.map.needsUpdate = true;
        }
        anyMat.needsUpdate = true;
      }
    });

    scene.add(loaded.scene);
    vrm = loaded;
    mixer = new THREE.AnimationMixer(loaded.scene);

    try {
      const idleClip = await loadMixamoAnimation(IDLE_URL, loaded, {
        name: "idle",
        omitBones: FACE_LOCK_BONES,
      });
      if (destroyed) return;
      idleAction = mixer.clipAction(idleClip);
      idleAction.setLoop(THREE.LoopRepeat, Infinity);
      idleAction.timeScale = 0.85;
      idleAction.play();
    } catch (err) {
      console.error("[pet] idle 加载失败", err);
    }

    try {
      if (loadWalk) {
        const walkClip = await loadMixamoAnimation(WALK_URL, loaded, {
          name: "walk",
          inPlace: true,
          omitBones: FACE_LOCK_BONES,
        });
        if (destroyed) return;
        walkAction = mixer.clipAction(walkClip);
        walkAction.setLoop(THREE.LoopRepeat, Infinity);
        walkAction.timeScale = 0.9;
        walkAction.enabled = true;
        walkAction.setEffectiveWeight(0);
      }
    } catch (err) {
      console.error("[pet] walk 加载失败", err);
    }

    if (mixer && idleAction) {
      mixer.update(1 / 30);
      loaded.update(1 / 30);
    }

    loaded.update(0);
    if (framing === "presence") {
      applyPresenceFraming(
        container.clientWidth || 1,
        container.clientHeight || 1,
        true
      );
    } else {
      onResize();
    }
    scheduleTick();
  })();

  return {
    ready,
    setActive,
    setLocomotion,
    notice,
    setExpression,
    pulseSpeak,
    clearSpeak,
    destroy() {
      destroyed = true;
      speakClock.clear();
      cancelAnimationFrame(raf);
      window.clearTimeout(resizeTimer);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("qi-window-resizing", onWindowResizing);
      window.removeEventListener("qi-layout-settled", onLayoutSettled);
      mixer?.stopAllAction();
      mixer = null;
      idleAction = null;
      walkAction = null;
      if (vrm) {
        scene.remove(vrm.scene);
        VRMUtils.deepDispose(vrm.scene);
        vrm = null;
      }
      if (renderer) {
        renderer.dispose();
        renderer.domElement.remove();
        renderer = null;
      }
    },
  };
}

function applyBlink(model: VRM, t: number) {
  const phase = t % 3.8;
  let blink = 0;
  if (phase < 0.07) blink = phase / 0.07;
  else if (phase < 0.14) blink = 1 - (phase - 0.07) / 0.07;
  model.expressionManager?.setValue("blink", blink);
}

function clearEyeBlink(model: VRM) {
  const em = model.expressionManager;
  if (!em) return;
  em.setValue("blink", 0);
  em.setValue("blinkLeft", 0);
  em.setValue("blinkRight", 0);
}

/** 按输出时钟写入 expression（供 vrm.update）；可见放大见 exaggerateMouthVisibility。 */
function applyMouthFromClock(
  model: VRM,
  weights: Record<MouthShape, number>,
  active: boolean
) {
  const em = model.expressionManager;
  if (!em) return;
  for (const name of MOUTH_SHAPES) {
    em.setValue(name, active ? Math.min(1, Math.max(0, weights[name] ?? 0)) : 0);
  }
}

/** 全身取景口型：放大 Face morph，硬顶；说话时清冲突嘴形。 */
function exaggerateMouthVisibility(
  model: VRM,
  weights: Record<MouthShape, number>,
  active: boolean
) {
  model.scene.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || !mesh.morphTargetDictionary || !mesh.morphTargetInfluences) {
      return;
    }
    if (!mesh.name.startsWith("Face")) return;
    if (active) {
      for (const conflict of MOUTH_CONFLICT_MORPHS) {
        const cidx = mesh.morphTargetDictionary[conflict];
        if (cidx != null) mesh.morphTargetInfluences[cidx] = 0;
      }
    }
    for (const shape of MOUTH_SHAPES) {
      const morphName = SHAPE_TO_MORPH[shape];
      const idx = mesh.morphTargetDictionary[morphName];
      if (idx == null) continue;
      const raw = active ? Math.min(1, Math.max(0, weights[shape] ?? 0)) : 0;
      mesh.morphTargetInfluences[idx] = Math.min(
        MOUTH_WEIGHT_CAP,
        raw * MOUTH_VISUAL_AMP
      );
    }
  });
}

function applyFaceExpression(
  model: VRM,
  expr: PetFaceExpression,
  current: Record<string, number>,
  delta: number
) {
  const em = model.expressionManager;
  if (!em) return;

  const targets = EXPR_TARGETS[expr] ?? {};
  const speed = 3.2; // ~0.5s 到目标
  const t = 1 - Math.exp(-speed * Math.max(delta, 0));

  for (const name of EMOTION_EXPR_NAMES) {
    const goal = targets[name] ?? 0;
    const prev = current[name] ?? 0;
    const next = prev + (goal - prev) * t;
    current[name] = Math.abs(next) < 0.002 ? 0 : next;
    em.setValue(name, current[name]);
  }
}

/** 正脸点击：看向你 + 身体微晃。不用 happy（Joy 会眯眼，很像眨眼/不屑） */
function applyNoticeReaction(
  model: VRM,
  now: number,
  start: number,
  until: number
) {
  if (until <= start || now >= until) return;

  const total = until - start;
  const elapsed = now - start;
  const remain = until - now;
  const rise = Math.min(0.22, total * 0.12);
  const fall = Math.min(0.55, total * 0.28);
  let w = 1;
  if (elapsed < rise) w = elapsed / rise;
  else if (remain < fall) w = remain / fall;
  w = Math.max(0, Math.min(1, w));

  // 叠在待机姿势上：极轻侧倾 + 微前倾
  const spine = model.humanoid?.getNormalizedBoneNode("spine");
  const chest = model.humanoid?.getNormalizedBoneNode("chest");
  const sway = Math.sin(elapsed * 2.6) * 0.028 * w;
  if (spine) {
    spine.rotation.z += sway;
    spine.rotation.x += 0.012 * w;
  }
  if (chest) {
    chest.rotation.z += sway * 0.55;
    chest.rotation.x += 0.01 * w;
  }
}

function frameCamera(
  camera: THREE.PerspectiveCamera,
  model: VRM,
  framing: PetVrmFraming = "pet",
  presenceCache?: {
    offsetX: number;
    cameraY: number;
    lookY: number;
    centerZ: number;
    dist: number;
    near: number;
    far: number;
  }
) {
  model.scene.position.set(0, 0, 0);
  model.scene.updateMatrixWorld(true);

  let box = new THREE.Box3().setFromObject(model.scene);
  if (box.isEmpty()) return;

  if (framing === "presence") {
    const preCenter = box.getCenter(new THREE.Vector3());
    model.scene.position.x = -preCenter.x;
    model.scene.updateMatrixWorld(true);
    box.setFromObject(model.scene);
  }

  const fullSize = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const focusX = framing === "presence" ? 0 : center.x;

  let fitH: number;
  let fitW: number;
  let distScale: number;
  let cameraY: number;
  let lookY: number;

  if (framing === "presence") {
    // 相处页：全身入镜，略留边；比先前更近，人物更大
    const footPad = fullSize.y * 0.09;
    const headPad = fullSize.y * 0.03;
    const frameMinY = box.min.y - footPad;
    const frameMaxY = box.max.y + headPad;
    const frameH = frameMaxY - frameMinY;
    const frameCenterY = (frameMinY + frameMaxY) * 0.5;

    fitH = Math.max(frameH * 1.02, 0.98);
    fitW = Math.max(fullSize.x * 1.03, 0.44);
    distScale = 0.93;
    cameraY = frameCenterY + fullSize.y * 0.008;
    lookY = frameCenterY + fullSize.y * 0.015;
  } else {
    fitH = Math.max(fullSize.y * 1.22, 0.9);
    fitW = Math.max(fullSize.x * 1.22, 0.4);
    distScale = 1.05;
    cameraY = center.y + fullSize.y * 0.02;
    lookY = center.y - fullSize.y * 0.04;
  }

  const vFov = THREE.MathUtils.degToRad(camera.fov);
  const distH = fitH / 2 / Math.tan(vFov / 2);
  const distW = fitW / 2 / Math.tan(vFov / 2) / Math.max(camera.aspect, 0.2);
  const dist =
    framing === "presence"
      ? distH * distScale
      : Math.max(distH, distW) * distScale;

  camera.position.set(focusX, cameraY, center.z + dist);
  camera.near = Math.max(0.05, dist / 80);
  camera.far = Math.max(40, dist * 12);
  camera.lookAt(focusX, lookY, center.z);
  camera.updateProjectionMatrix();

  if (framing === "presence" && presenceCache) {
    presenceCache.offsetX = model.scene.position.x;
    presenceCache.cameraY = cameraY;
    presenceCache.lookY = lookY;
    presenceCache.centerZ = center.z;
    presenceCache.dist = dist;
    presenceCache.near = camera.near;
    presenceCache.far = camera.far;
  }
}
