"use client";

import React, { useState, useRef, useEffect } from "react";
import { VoiceProsodySignals } from "@/lib/api";

interface VoiceRecorderProps {
  onAudioReady?: (blob: Blob) => void;
  onSubmitVoice?: (blob: Blob) => Promise<void>;
  isSubmitting?: boolean;
  prosodySignals?: VoiceProsodySignals | null;
  label?: string;
  submitButtonText?: string;
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  onAudioReady,
  onSubmitVoice,
  isSubmitting = false,
  prosodySignals,
  label = "Explain Out Loud (Voice Protégé Mode)",
  submitButtonText = "Submit Spoken Explanation",
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [volumeLevel, setVolumeLevel] = useState<number>(0);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Clean up audio URL and contexts on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, [audioUrl]);

  const startRecording = async () => {
    setPermissionError(null);
    setAudioBlob(null);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Setup Web Audio Analyser for live visualizer
      try {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new AudioCtx();
        audioContextRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateMeter = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          setVolumeLevel(Math.min(100, Math.round((avg / 128) * 100)));
          animFrameRef.current = requestAnimationFrame(updateMeter);
        };
        updateMeter();
      } catch {
        // Fallback gracefully if Web Audio Analyser fails
      }

      // Setup MediaRecorder
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";

      const options = mimeType ? { mimeType } : undefined;
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Stop audio tracks
        stream.getTracks().forEach((t) => t.stop());
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current);
        }
        setVolumeLevel(0);

        const finalBlob = new Blob(audioChunksRef.current, {
          type: mimeType || "audio/webm",
        });
        setAudioBlob(finalBlob);
        const url = URL.createObjectURL(finalBlob);
        setAudioUrl(url);

        if (onAudioReady) {
          onAudioReady(finalBlob);
        }
      };

      mediaRecorder.start(250); // Collect slices every 250ms
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setPermissionError(`Microphone access denied: ${msg}. Check browser permissions.`);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
  };

  const handleReRecord = () => {
    setAudioBlob(null);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    setRecordingSeconds(0);
    startRecording();
  };

  const handleSubmit = async () => {
    if (!audioBlob || !onSubmitVoice) return;
    await onSubmitVoice(audioBlob);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex flex-col gap-4 p-5 rounded-2xl bg-neutral-900/80 border border-purple-500/30 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-xl bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center justify-center text-sm">
            🎙️
          </span>
          <div>
            <h4 className="text-sm font-bold text-white tracking-wide">{label}</h4>
            <p className="text-xs text-neutral-400">
              Speak naturally. Local Whisper extracts causal depth, cadence, and pause cues.
            </p>
          </div>
        </div>

        {isRecording && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-mono font-semibold animate-pulse">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span>RECORDING {formatTime(recordingSeconds)}</span>
          </div>
        )}
      </div>

      {permissionError && (
        <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300">
          ⚠️ {permissionError}
        </div>
      )}

      {/* Live Volume Meter Bar */}
      {isRecording && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px] font-mono text-neutral-400">
            <span>Input Voice Volume</span>
            <span>{volumeLevel}%</span>
          </div>
          <div className="w-full h-2 rounded-full bg-neutral-950 overflow-hidden border border-neutral-800">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 via-purple-500 to-rose-500 transition-all duration-75"
              style={{ width: `${Math.max(4, volumeLevel)}%` }}
            />
          </div>
        </div>
      )}

      {/* Audio Playback Preview */}
      {audioUrl && !isRecording && (
        <div className="flex flex-col gap-2 p-3 rounded-xl bg-neutral-950 border border-neutral-800">
          <span className="text-xs font-medium text-neutral-400">Review Your Spoken Teaching:</span>
          <audio src={audioUrl} controls className="w-full h-10 rounded-lg outline-none" />
        </div>
      )}

      {/* Action Controls */}
      <div className="flex items-center justify-between gap-3 pt-1">
        {!isRecording && !audioBlob && (
          <button
            type="button"
            onClick={startRecording}
            className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs transition-all shadow-lg shadow-purple-600/20 flex items-center gap-2"
          >
            <span>🎙️</span>
            <span>Start Voice Recording</span>
          </button>
        )}

        {isRecording && (
          <button
            type="button"
            onClick={stopRecording}
            className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition-all shadow-lg shadow-rose-600/20 flex items-center gap-2"
          >
            <span>⏹️</span>
            <span>Stop Recording ({formatTime(recordingSeconds)})</span>
          </button>
        )}

        {audioBlob && !isRecording && (
          <div className="flex items-center gap-3 w-full justify-between">
            <button
              type="button"
              onClick={handleReRecord}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-semibold text-xs border border-neutral-700 transition"
            >
              🔄 Re-record
            </button>

            {onSubmitVoice && (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-purple-600/25 transition disabled:opacity-50 flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <span className="animate-spin text-sm">⏳</span>
                    <span>Analyzing Prosody & Reasoning...</span>
                  </>
                ) : (
                  <>
                    <span>🚀</span>
                    <span>{submitButtonText}</span>
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Prosody Telemetry Badges */}
      {prosodySignals && (
        <div className="mt-2 p-4 rounded-xl bg-neutral-950 border border-purple-500/30 flex flex-col gap-2.5">
          <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
            <span className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
              <span>🧠</span> Spoken Cognitive Signals (Local Whisper)
            </span>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                prosodySignals.monotone_recitation_flag
                  ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                  : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
              }`}
            >
              {prosodySignals.fluency_signal ||
                (prosodySignals.monotone_recitation_flag
                  ? "Rushed Recitation"
                  : "Natural Causal Fluency")}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 text-xs">
            <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
              <span className="text-neutral-500 block text-[10px] uppercase">Speech Rate</span>
              <span className="font-mono font-bold text-white text-sm">
                {Math.round(prosodySignals.speech_rate_wpm)} <span className="text-xs text-neutral-400 font-normal">WPM</span>
              </span>
            </div>

            <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
              <span className="text-neutral-500 block text-[10px] uppercase">Hesitation Pauses</span>
              <span className="font-mono font-bold text-purple-300 text-sm">
                {prosodySignals.hesitation_pause_count} <span className="text-xs text-neutral-400 font-normal">(&gt;1.5s)</span>
              </span>
            </div>

            <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
              <span className="text-neutral-500 block text-[10px] uppercase">Filler Word Ratio</span>
              <span className="font-mono font-bold text-amber-300 text-sm">
                {(prosodySignals.filler_word_ratio * 100).toFixed(1)}%
              </span>
            </div>

            <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
              <span className="text-neutral-500 block text-[10px] uppercase">Self-Corrections</span>
              <span className="font-mono font-bold text-emerald-400 text-sm">
                {prosodySignals.self_correction_count}
              </span>
            </div>
          </div>

          {prosodySignals.transcript && (
            <div className="text-xs text-neutral-300 bg-neutral-900 p-2.5 rounded-lg border border-neutral-800/80 mt-1">
              <span className="text-neutral-500 font-mono text-[10px] block mb-1">PROSODY TRANSCRIPTION:</span>
              &ldquo;{prosodySignals.transcript}&rdquo;
            </div>
          )}
        </div>
      )}
    </div>
  );
};
