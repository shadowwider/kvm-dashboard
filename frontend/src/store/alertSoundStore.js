import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ALERT_SEVERITIES } from '../utils/alertSound';

const defaultSeverities = Object.fromEntries(
    ALERT_SEVERITIES.map((severity) => [severity, true])
);

export const useAlertSoundStore = create(
    persist(
        (set) => ({
            muted: false,
            severities: defaultSeverities,
            audioStatus: 'idle',
            setMuted: (muted) => set({ muted }),
            toggleMuted: () => set((state) => ({ muted: !state.muted })),
            setSeverityEnabled: (severity, enabled) => set((state) => ({
                severities: { ...state.severities, [severity]: enabled },
            })),
            setAudioStatus: (audioStatus) => set({ audioStatus }),
        }),
        {
            name: 'kvm-alert-sound-settings',
            partialize: (state) => ({
                muted: state.muted,
                severities: state.severities,
            }),
        }
    )
);
