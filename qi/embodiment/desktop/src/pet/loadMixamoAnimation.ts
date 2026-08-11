import * as THREE from "three";
import { FBXLoader } from "three/addons/loaders/FBXLoader.js";
import type { VRM } from "@pixiv/three-vrm";
import { mixamoVRMRigMap } from "./mixamoVRMRigMap";

export type MixamoLoadOptions = {
  /** 剪辑名 */
  name?: string;
  /** 去掉位移轨，用于窗体移动时的原地走 */
  inPlace?: boolean;
  /** 去掉头/颈等，避免 VRoid 脸上出现「嚼嘴」 */
  omitBones?: string[];
};

/**
 * 加载 Mixamo FBX 并重定向到 VRM 归一化骨骼。
 * 改编自 pixiv/three-vrm examples/humanoidAnimation/loadMixamoAnimation.js
 */
export async function loadMixamoAnimation(
  url: string,
  vrm: VRM,
  options: MixamoLoadOptions = {}
): Promise<THREE.AnimationClip> {
  const { name = "mixamo", inPlace = false, omitBones = [] } = options;
  const omit = new Set(omitBones);
  const loader = new FBXLoader();
  const asset = await loader.loadAsync(url);

  const clip =
    THREE.AnimationClip.findByName(asset.animations, "mixamo.com") ??
    asset.animations[0];
  if (!clip) {
    throw new Error(`FBX 中没有动画剪辑: ${url}`);
  }

  const tracks: THREE.KeyframeTrack[] = [];
  const restRotationInverse = new THREE.Quaternion();
  const parentRestWorldRotation = new THREE.Quaternion();
  const _quatA = new THREE.Quaternion();

  const motionHips =
    asset.getObjectByName("mixamorigHips") ??
    asset.getObjectByName("mixamorig:Hips");
  const motionHipsHeight = motionHips?.position.y;
  const vrmHipsY = vrm.humanoid?.normalizedRestPose?.hips?.position?.[1];
  if (motionHipsHeight == null || vrmHipsY == null || motionHipsHeight === 0) {
    throw new Error("无法计算 Mixamo→VRM 髋部缩放");
  }
  const hipsPositionScale = vrmHipsY / motionHipsHeight;

  for (const track of clip.tracks) {
    const trackSplitted = track.name.split(".");
    const rawName = trackSplitted[0] ?? "";
    const propertyName = trackSplitted[1];
    if (!propertyName) continue;

    const mixamoRigName = normalizeMixamoName(rawName);
    const vrmBoneName = mixamoVRMRigMap[mixamoRigName];
    if (!vrmBoneName || omit.has(vrmBoneName)) continue;

    const vrmNodeName = vrm.humanoid?.getNormalizedBoneNode(
      vrmBoneName as never
    )?.name;
    const mixamoRigNode =
      asset.getObjectByName(rawName) ?? asset.getObjectByName(mixamoRigName);
    if (vrmNodeName == null || !mixamoRigNode?.parent) continue;

    mixamoRigNode.getWorldQuaternion(restRotationInverse).invert();
    mixamoRigNode.parent.getWorldQuaternion(parentRestWorldRotation);

    if (track instanceof THREE.QuaternionKeyframeTrack) {
      const values = track.values.slice();
      for (let i = 0; i < values.length; i += 4) {
        const flat = values.slice(i, i + 4);
        _quatA.fromArray(flat);
        _quatA.premultiply(parentRestWorldRotation).multiply(restRotationInverse);
        _quatA.toArray(flat);
        values[i] = flat[0]!;
        values[i + 1] = flat[1]!;
        values[i + 2] = flat[2]!;
        values[i + 3] = flat[3]!;
      }

      const metaVersion = vrm.meta?.metaVersion;
      tracks.push(
        new THREE.QuaternionKeyframeTrack(
          `${vrmNodeName}.${propertyName}`,
          track.times,
          values.map((v, i) => (metaVersion === "0" && i % 2 === 0 ? -v : v))
        )
      );
    } else if (track instanceof THREE.VectorKeyframeTrack) {
      if (inPlace) continue;
      const metaVersion = vrm.meta?.metaVersion;
      const value = track.values.map(
        (v, i) =>
          (metaVersion === "0" && i % 3 !== 1 ? -v : v) * hipsPositionScale
      );
      tracks.push(
        new THREE.VectorKeyframeTrack(
          `${vrmNodeName}.${propertyName}`,
          track.times,
          value
        )
      );
    }
  }

  return new THREE.AnimationClip(name, clip.duration, tracks);
}

/** Mixamo 导出常见 `mixamorig:Head` / `mixamorigHead` 两种 */
function normalizeMixamoName(name: string): string {
  return name.replace(/^mixamorig:/, "mixamorig");
}
