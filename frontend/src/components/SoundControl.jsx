import { useState } from 'react';
import { BellRing, Play, Volume2, VolumeX, X } from 'lucide-react';
import { useTranslation } from '../i18n';
import { useAlertSoundStore } from '../store/alertSoundStore';
import { ALERT_SEVERITIES } from '../utils/alertSound';
import { playAlertTone } from '../hooks/useAlertSound';

export default function SoundControl() {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const {
        audioStatus,
        muted,
        severities,
        setAudioStatus,
        setMuted,
        setSeverityEnabled,
    } = useAlertSoundStore();

    const preview = async () => {
        try {
            await playAlertTone('warning');
            setAudioStatus('ready');
        } catch {
            setAudioStatus('blocked');
        }
    };

    return (
        <div className="sound-control">
            <button
                className={`ua-btn ${muted ? 'muted' : ''}`}
                onClick={() => setOpen((value) => !value)}
                title={t('sound.settings')}
                aria-label={t('sound.settings')}
            >
                {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>

            {open && (
                <div className="sound-popover">
                    <div className="sound-popover-header">
                        <span><BellRing size={14} /> {t('sound.title')}</span>
                        <button
                            className="icon-button"
                            onClick={() => setOpen(false)}
                            title={t('common.close')}
                            aria-label={t('common.close')}
                        >
                            <X size={14} />
                        </button>
                    </div>

                    <label className="sound-master-row">
                        <span>{t('sound.muted')}</span>
                        <input
                            type="checkbox"
                            checked={muted}
                            onChange={(event) => setMuted(event.target.checked)}
                        />
                    </label>

                    <div className="sound-severity-list">
                        {ALERT_SEVERITIES.map((severity) => (
                            <label key={severity} className="sound-severity-row">
                                <span className={`status-dot ${severity}`} />
                                <span>{t(`sound.severities.${severity}`)}</span>
                                <input
                                    type="checkbox"
                                    checked={severities[severity] !== false}
                                    onChange={(event) => setSeverityEnabled(severity, event.target.checked)}
                                />
                            </label>
                        ))}
                    </div>

                    <button className="sound-preview-button" onClick={preview}>
                        <Play size={13} /> {t('sound.preview')}
                    </button>
                    {audioStatus === 'ready' && (
                        <div className="sound-help" role="status">{t('sound.ready')}</div>
                    )}
                    {audioStatus === 'blocked' && (
                        <div className="sound-help" role="alert">{t('sound.blocked')}</div>
                    )}
                </div>
            )}
        </div>
    );
}
