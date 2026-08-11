import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { loadMixamoAnimation } from "./loadMixamoAnimation";

const MODEL_URL = "/avatars/qi-avatar.vrm";
const IDLE_URL = "/animations/idle.fbx";
const WALK_URL = "/animations/walk.fbx";

export type PetLocomotion = "idle" | "walk";
/** 1 = 向屏幕右走，-1 = 向左 */
export type PetFacing = 1 | -1;

export type PetVrmHandle = {
  ready: Promise<void>;
  destroy: () => void;
  setLocomotion: (mode: PetLocomotion, facing?: PetFacing) => void;
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
  let raf = 0;

  const clock = new THREE.Clock();
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 40);

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
      applyBlink(vrm, clock.elapsedTime);
      vrm.update(delta);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();
  })();

  return {
    ready,
    setLocomotion,
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
