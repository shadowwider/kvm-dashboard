import { useEffect } from 'react';
import { useStore } from '../store/mainStore';
import { useAlertSoundStore } from '../store/alertSoundStore';
import { liveAlertSoundGate, playToneWithContext } from '../utils/alertSound';

let audioContext;

function getAudioContext() {
    if (typeof window === 'undefined') return null;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return null;
    audioContext ||= new AudioContext();
    return audioContext;
}

export function createAlertTonePlayer(resolveContext = getAudioContext) {
    return async function playAlertTone(severity = 'info') {
        await playToneWithContext(resolveContext(), severity);
    };
}

export const playAlertTone = createAlertTonePlayer();

export default function useAlertSound() {
    const soundEvents = useStore((state) => state.soundEvents);
    const muted = useAlertSoundStore((state) => state.muted);
    const severities = useAlertSoundStore((state) => state.severities);
    const setAudioStatus = useAlertSoundStore((state) => state.setAudioStatus);

    useEffect(() => {
        soundEvents.forEach((alert) => {
            const decision = liveAlertSoundGate.evaluate(alert, { muted, severities });
            if (!decision.play) return;
            playAlertTone(decision.severity)
                .then(() => setAudioStatus('ready'))
                .catch(() => setAudioStatus('blocked'));
        });
    }, [muted, setAudioStatus, severities, soundEvents]);
}
