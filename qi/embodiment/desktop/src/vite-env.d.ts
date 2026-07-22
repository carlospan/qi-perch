/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

declare module "pixi-live2d-display/cubism4" {
  import type { Container } from "pixi.js";
  export class Live2DModel extends Container {
    static registerTicker(ticker: unknown): void;
    static from(src: string, options?: object): Promise<Live2DModel>;
    motion(group: string, index?: number): Promise<void> | void;
    internalModel: {
      coreModel: {
        getParameterMinimumValue(id: string): number;
        getParameterMaximumValue(id: string): number;
        getParameterDefaultValue(id: string): number;
        setParameterValueById(id: string, value: number): void;
      };
    };
    anchor: { set(x: number, y: number): void };
  }
}

interface Window {
  Live2DCubismCore?: unknown;
}
