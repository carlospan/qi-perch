import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { loadMixamoAnimation } from "./loadMixamoAnimation";

const MODEL_URL = "/avatars/qi-avatar.vrm";
const IDLE_URL = "/animations/idle.fbx";
const WALK_URL = "/animations/walk.fbx";
/** 去掉头颈动画，避免 VRoid 脸被带出张嘴感 */
const FACE_LOCK_BONES = ["head", "neck", "jaw"];
const MOUTH_EXPR = ["aa", "ih", "ou", "ee", "oh"] as const;

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

/** 目标权重：happy 故意压低，避免 VRoid Joy 眯眼 */
const EXPR_TARGETS: Record<PetFaceExpression, Record<string, number>> = {
  neutral: {},
  soft_smile: { soft_smile: 1 },
  happy: { happy: 0.38 },
  quiet: { quiet: 1 },
  surprised: { surprised: 0.72 },
  sleepy: { sleepy: 1 },
  curious: { curious: 1 },
};

export type PetVrmHandle = {
  ready: Promise<void>;
  destroy: () => void;
  setLocomotion: (mode: PetLocomotion, facing?: PetFacing) => void;
  /** 被点及时：看向你 + 身体微晃（不用 Joy 浅笑，会眯眼像眨眼） */
  notice: (durationMs?: number) => void;
  /** 情绪脸：后端 avatar_state.expression → VRM preset/custom */
  setExpression: (expression: string) => void;
};

/**
 * 透明桌宠：VRM + 待机/走路切换 + 眨眼。
 */
export function createPetVrm(container: HTMLElement): PetVrmHandle {
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
  let faceExpr: PetFaceExpression = "neutral";
  /** 当前已应用到模型的权重，向目标缓动 */
  const faceWeights: Record<string, number> = {};

  const clock = new THREE.Clock();
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 40);
  /** 视线落点：在脸前方朝向你，避免直接盯相机节点 */
  const lookAtTarget = new THREE.Object3D();
  scene.add(lookAtTarget);
  const _headPos = new THREE.Vector3();
  const _camDir = new THREE.Vector3();

  const key = new THREE.DirectionalLight(0xffffff, 1.2);
  key.position.set(0.45, 1.6, 1.4);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xddeeff, 0.45);
  fill.position.set(-0.8, 0.6, 0.6);
  scene.add(fill);
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));

  const onResize = () => {
    if (!renderer || destroyed) return;
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (vrm) frameCamera(camera, vrm);
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
    frameCamera(camera, vrm);
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

  const updateLookAtTarget = () => {
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
    lookAtTarget.position.copy(_headPos).addScaledVector(_camDir, 0.45);
  };

  const ready = (async () => {
    renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      premultipliedAlpha: false,
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    window.addEventListener("resize", onResize);

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    const gltf = await loader.loadAsync(MODEL_URL);
    if (destroyed) return;

    const loaded = gltf.userData.vrm as VRM;
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons(gltf.scene);
    VRMUtils.rotateVRM0(loaded);

    loaded.scene.traverse((obj) => {
      obj.frustumCulled = false;
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
    } catch (err) {
      console.error("[pet] walk 加载失败", err);
    }

    if (mixer && idleAction) {
      mixer.update(1 / 30);
      loaded.update(1 / 30);
    }

    loaded.update(0);
    onResize();

    const tick = () => {
      if (destroyed || !renderer || !vrm) return;
      const delta = clock.getDelta();
      mixer?.update(delta);
      lockMouth(vrm);
      const noticing = clock.elapsedTime < noticeUntil;
      if (noticing) {
        updateLookAtTarget();
        applyNoticeReaction(vrm, clock.elapsedTime, noticeStart, noticeUntil);
        clearEyeBlink(vrm);
      } else {
        // sleepy 自带半闭眼，减弱自动眨眼以免打架
        if (faceExpr === "sleepy") {
          clearEyeBlink(vrm);
        } else {
          applyBlink(vrm, clock.elapsedTime);
        }
        if (vrm.lookAt) vrm.lookAt.target = null;
      }
      applyFaceExpression(vrm, faceExpr, faceWeights, delta);
      vrm.update(delta);
      // Joy/update 之后再清一次，避免眯眼被当成眨眼
      if (noticing) {
        clearEyeBlink(vrm);
        vrm.expressionManager?.update();
      }
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();
  })();

  return {
    ready,
    setLocomotion,
    notice,
    setExpression,
    destroy() {
      destroyed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
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

function lockMouth(model: VRM) {
  const em = model.expressionManager;
  if (!em) return;
  for (const name of MOUTH_EXPR) {
    em.setValue(name, 0);
  }
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

function frameCamera(camera: THREE.PerspectiveCamera, model: VRM) {
  model.scene.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model.scene);
  if (box.isEmpty()) return;

  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const padding = 1.22;
  const fitH = Math.max(size.y * padding, 0.9);
  const fitW = Math.max(size.x * padding, 0.4);

  const vFov = THREE.MathUtils.degToRad(camera.fov);
  const distH = fitH / 2 / Math.tan(vFov / 2);
  const distW = fitW / 2 / Math.tan(vFov / 2) / Math.max(camera.aspect, 0.2);
  const dist = Math.max(distH, distW) * 1.05;

  camera.position.set(center.x, center.y + size.y * 0.02, center.z + dist);
  camera.near = Math.max(0.05, dist / 80);
  camera.far = Math.max(40, dist * 12);
  camera.lookAt(center.x, center.y - size.y * 0.04, center.z);
  camera.updateProjectionMatrix();
}
