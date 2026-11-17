import { defineStore } from 'pinia'
import type {
  CompassReading,
  InputMethod,
  NorthType,
  SceneMode,
} from '@/core/types'

export interface CompassDraft {
  facingDeg: number
  inputMethod: InputMethod
  stability: number
  uncertainty: number
  northType: NorthType
  declination: number
  city: string
  confirmed: boolean
}

const initialCompass: CompassDraft = {
  facingDeg: 180,
  inputMethod: 'MANUAL_DEG',
  stability: 100,
  uncertainty: 0.5,
  northType: 'MAGNETIC',
  declination: 0,
  city: '',
  confirmed: false,
}

export const useDraftStore = defineStore('draft', {
  state: () => ({
    compass: { ...initialCompass } as CompassDraft,
    sceneMode: 'YANG' as SceneMode,
  }),
  actions: {
    setCompass(draft: Partial<CompassDraft>): void {
      this.compass = { ...this.compass, ...draft }
    },
    setSceneMode(mode: SceneMode): void {
      this.sceneMode = mode
    },
    toReading(): CompassReading {
      return {
        facingDeg: this.compass.facingDeg,
        mountDeg: (this.compass.facingDeg + 180) % 360,
        northType: this.compass.northType,
        declination: this.compass.declination,
        stability: this.compass.stability,
        inputMethod: this.compass.inputMethod,
        uncertainty: this.compass.uncertainty,
      }
    },
    reset(): void {
      this.compass = { ...initialCompass }
      this.sceneMode = 'YANG'
    },
  },
})
