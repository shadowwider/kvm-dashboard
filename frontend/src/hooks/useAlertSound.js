import { useEffect } from 'react';
import { useStore } from '../store/mainStore';
import { useAlertSoundStore } from '../store/alertSoundStore';
import { getToneSpec, liveAlertSoundGate } from '../utils/alertSound';

let audioContext;

function getAudioContext() {
    if (typeof window === 'undefined') return null;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return null;
    audioContext ||= new AudioContext();
    return audioContext;
}

export async function playAlertTone(severity = 'info') {
    const context = getAudioContext();
    if (!context) throw new Error('audio_unsupported');
    if (context.state === 'suspended') await context.resume();

    const { duration, frequency, gain } = getToneSpec(severity);
    const oscillator = context.createOscillator();
    const volume = context.createGain();
    const start = context.currentTime;

    oscillator.type = severity === 'critical' || severity === 'offline' ? 'square' : 'sine';
    oscillator.frequency.setValueAtTime(frequency, start);
    volume.gain.setValueAtTime(0.0001, start);
    volume.gain.exponentialRampToValueAtTime(gain, start + 0.015);
    volume.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(volume);
    volume.connect(context.destination);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
}

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
