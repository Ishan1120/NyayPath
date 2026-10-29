'use client';

import React, { useState, useRef, useEffect } from 'react';
import { 
  Mic, 
  Square, 
  Loader2, 
  Volume2, 
  AlertCircle, 
  Upload, 
  HelpCircle, 
  Check, 
  X, 
  ExternalLink,
  Sparkles
} from 'lucide-react';
import { transcribeAudio } from '@/lib/api';

interface AudioRecorderProps {
  onTranscription: (text: string) => void;
  language?: string;
}

export default function AudioRecorder({ onTranscription, language = "English" }: AudioRecorderProps) {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [isInsecureOrigin, setIsInsecureOrigin] = useState(false);
  const [uploadingAudio, setUploadingAudio] = useState(false);

  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Check if browser context is secure on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isLocalhost = window.location.hostname === 'localhost';
      const isHttps = window.location.protocol === 'https:';
      const isSecure = window.isSecureContext === true;

      // Chrome/Edge strictly require true HTTPS or literal http://localhost for microphone & Web Speech API
      if (!isHttps && (!isLocalhost || !isSecure)) {
        setIsInsecureOrigin(true);
      }
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  const handleSwitchToLocalhost = () => {
    if (typeof window !== 'undefined') {
      const port = window.location.port ? `:${window.location.port}` : '';
      const newUrl = `http://localhost${port}${window.location.pathname}${window.location.search}`;
      window.location.href = newUrl;
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // ENGINE 1: NATIVE WEB SPEECH API (Chrome, Edge, Brave)
  // ──────────────────────────────────────────────────────────────────────────
  const startWebSpeech = () => {
    setErrorMessage(null);
    setInterimText('');
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      startMediaRecorderFallback();
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      // Locale selection
      if (language === 'Hindi') {
        recognition.lang = 'hi-IN';
      } else {
        recognition.lang = 'en-IN';
      }

      recognition.onstart = () => {
        setIsListening(true);
        setIsProcessing(false);
      };

      recognition.onresult = (event: any) => {
        let liveInterim = '';
        let finalized = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalized += transcript + ' ';
          } else {
            liveInterim += transcript;
          }
        }

        if (finalized.trim()) {
          onTranscription(finalized.trim());
        }
        setInterimText(liveInterim || finalized);
      };

      recognition.onerror = (event: any) => {
        console.warn('SpeechRecognition error:', event.error);
        if (event.error === 'not-allowed') {
          setErrorMessage('Microphone access blocked. Click the lock/tune icon in your address bar to allow.');
          setShowHelpModal(true);
          setIsListening(false);
        } else if (event.error === 'service-not-allowed') {
          setErrorMessage('Speech service not allowed by browser. Please use http://localhost:3000.');
          setShowHelpModal(true);
          setIsListening(false);
        } else if (event.error === 'network') {
          recognition.stop();
          startMediaRecorderFallback();
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterimText('');
      };

      recognition.start();
    } catch (err: any) {
      console.warn('Speech recognition start failed, using fallback:', err);
      startMediaRecorderFallback();
    }
  };

  const stopWebSpeech = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
    setIsListening(false);
    setInterimText('');
  };

  // ──────────────────────────────────────────────────────────────────────────
  // ENGINE 2: MEDIA RECORDER + SERVER WHISPER FALLBACK
  // ──────────────────────────────────────────────────────────────────────────
  const startMediaRecorderFallback = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorMessage('Microphone not supported on this connection. Please access via http://localhost:3000.');
      setShowHelpModal(true);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const mimeType = mediaRecorderRef.current?.mimeType || 'audio/webm';
        const audioBlob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];
        setIsProcessing(true);

        try {
          const res = await transcribeAudio(audioBlob, language);
          const resultText = res?.text || res?.transcription || '';
          if (resultText && !resultText.toLowerCase().includes('failed')) {
            onTranscription(resultText);
          } else {
            setErrorMessage('Could not process recording. You can also upload an audio file or type manually.');
          }
        } catch (e) {
          setErrorMessage('Transcription server unavailable. Please type manually.');
        } finally {
          setIsProcessing(false);
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
          }
        }
      };

      mediaRecorder.start();
      setIsListening(true);
    } catch (err: any) {
      console.warn('getUserMedia error:', err);
      setErrorMessage('Microphone access blocked. Click the lock/tune icon in the browser address bar to allow.');
      setShowHelpModal(true);
      setIsListening(false);
    }
  };

  const stopMediaRecorder = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
    setIsListening(false);
  };

  const handleToggle = () => {
    if (isInsecureOrigin) {
      setShowHelpModal(true);
      return;
    }

    if (isListening) {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition && recognitionRef.current) {
        stopWebSpeech();
      } else {
        stopMediaRecorder();
      }
    } else {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        startWebSpeech();
      } else {
        startMediaRecorderFallback();
      }
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // AUDIO FILE UPLOAD FALLBACK (For recorded memos / files)
  // ──────────────────────────────────────────────────────────────────────────
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingAudio(true);
    setErrorMessage(null);
    try {
      const res = await transcribeAudio(file, language);
      const resultText = res?.text || res?.transcription || '';
      if (resultText && !resultText.toLowerCase().includes('failed')) {
        onTranscription(resultText);
      } else {
        setErrorMessage('Could not transcribe uploaded audio. Please check file format.');
      }
    } catch (err) {
      setErrorMessage('Audio upload failed. Please type manually.');
    } finally {
      setUploadingAudio(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {/* Insecure Origin Alert Pill */}
      {isInsecureOrigin && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-amber-50 border border-amber-300 rounded-2xl text-xs text-amber-900 shadow-sm animate-fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-amber-600 shrink-0" />
            <span className="font-medium">
              Browser microphone blocked on this URL. Chrome strictly requires <strong>http://localhost:3000</strong>.
            </span>
          </div>
          <button
            type="button"
            onClick={handleSwitchToLocalhost}
            className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl shadow-xs transition-colors shrink-0 cursor-pointer text-center"
          >
            ⚡ Switch to Localhost:3000
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2.5">
        {/* Main Microphone Button */}
        <button
          type="button"
          onClick={handleToggle}
          disabled={isProcessing || uploadingAudio}
          className={`relative inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs sm:text-sm font-bold tracking-tight transition-all duration-200 cursor-pointer shadow-sm select-none ${
            isListening
              ? 'bg-gradient-to-r from-rose-600 to-red-600 text-white shadow-rose-500/40 shadow-md ring-4 ring-rose-500/20 animate-pulse'
              : isProcessing || uploadingAudio
              ? 'bg-slate-100 text-slate-500 border border-slate-200 cursor-not-allowed'
              : 'bg-white hover:bg-rose-50 text-slate-800 border border-slate-300 hover:border-court-maroon hover:text-court-maroon'
          }`}
          title={isListening ? 'Click to stop listening' : 'Speak your complaint'}
        >
          {isListening ? (
            <>
              <Square size={14} className="fill-current text-white animate-bounce" />
              <span>Listening... (Click to Stop)</span>
              {/* Animated sound bars */}
              <span className="flex items-center gap-0.5 ml-1">
                <span className="w-1 h-3 bg-white rounded-full animate-pulse" />
                <span className="w-1 h-4 bg-white rounded-full animate-pulse delay-75" />
                <span className="w-1 h-2 bg-white rounded-full animate-pulse delay-150" />
              </span>
            </>
          ) : isProcessing || uploadingAudio ? (
            <>
              <Loader2 size={14} className="animate-spin text-court-maroon" />
              <span>Transcribing Audio...</span>
            </>
          ) : (
            <>
              <Mic size={15} className="text-court-maroon" />
              <span>Speak Complaint ({language === 'Hindi' ? 'हिन्दी' : language})</span>
            </>
          )}
        </button>

        {/* Upload Audio File Option */}
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg"
          onChange={handleFileUpload}
          className="hidden"
          id="audio-file-upload"
        />
        <label
          htmlFor="audio-file-upload"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-bold bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-700 hover:text-slate-900 cursor-pointer transition-all shadow-xs"
          title="Upload audio memo (.mp3, .wav, .m4a)"
        >
          <Upload size={13} className="text-amber-600" />
          <span>Upload Audio File</span>
        </label>

        {/* Help icon */}
        <button
          type="button"
          onClick={() => setShowHelpModal(true)}
          className="p-2 rounded-full text-slate-500 hover:text-slate-800 hover:bg-slate-200/80 transition-colors cursor-pointer"
          title="Microphone permission help"
        >
          <HelpCircle size={15} />
        </button>

        {/* Live speech interim preview */}
        {isListening && interimText && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-full font-medium max-w-xs truncate animate-fade-in shadow-xs">
            <Volume2 size={12} className="shrink-0 text-rose-600 animate-pulse" />
            <span className="truncate italic">&quot;{interimText}&quot;</span>
          </div>
        )}
      </div>

      {/* Inline error notice */}
      {errorMessage && (
        <div className="flex items-center justify-between gap-2 text-xs text-rose-900 font-medium px-3.5 py-2 bg-rose-50 rounded-xl border border-rose-200 shadow-xs">
          <div className="flex items-center gap-1.5">
            <AlertCircle size={14} className="shrink-0 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setShowHelpModal(true)}
            className="underline font-bold text-rose-700 hover:text-rose-900 cursor-pointer shrink-0 ml-2"
          >
            Fix Permission
          </button>
        </div>
      )}

      {/* Permission Help Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-fade-in text-slate-900">
          <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-6 sm:p-7 border border-slate-200 relative text-left">
            <button
              onClick={() => setShowHelpModal(false)}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-700"
            >
              <X size={16} />
            </button>

            <div className="w-11 h-11 bg-rose-50 text-court-maroon rounded-2xl flex items-center justify-center mb-4">
              <Mic size={22} />
            </div>

            <h3 className="text-xl font-black text-ashoka-navy mb-2 tracking-tight">
              Enabling Microphone in Browser
            </h3>
            <p className="text-xs text-slate-600 mb-4 font-medium leading-relaxed">
              Modern browsers (Chrome, Edge, Brave) require secure connections to access the microphone. Follow these simple steps:
            </p>

            <div className="space-y-3 mb-6 text-xs text-slate-700">
              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="w-5 h-5 rounded-full bg-court-maroon text-white flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                  1
                </span>
                <div>
                  <strong className="block font-bold text-slate-900">Use http://localhost:3000</strong>
                  <span className="text-slate-500 leading-relaxed block mt-0.5">
                    Microphone is permanently blocked on IP addresses (e.g. <code>192.168.x.x</code>). Always open via <strong>localhost</strong>.
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="w-5 h-5 rounded-full bg-court-maroon text-white flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                  2
                </span>
                <div>
                  <strong className="block font-bold text-slate-900">Click the Site Settings / Tune Icon</strong>
                  <span className="text-slate-500 leading-relaxed block mt-0.5">
                    Look at the left edge of your browser URL bar. Click the <strong>Sliders / Lock</strong> icon 🔒 and set <strong>Microphone: Allow</strong>.
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="w-5 h-5 rounded-full bg-court-maroon text-white flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                  3
                </span>
                <div>
                  <strong className="block font-bold text-slate-900">Alternative: Upload Audio File</strong>
                  <span className="text-slate-500 leading-relaxed block mt-0.5">
                    You can also record on your phone or Windows Voice Recorder and click <strong>Upload Audio</strong> to transcribe automatically.
                  </span>
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleSwitchToLocalhost}
                className="flex-1 py-2.5 bg-court-maroon hover:bg-rose-800 text-white font-bold text-xs rounded-xl shadow-md cursor-pointer transition-colors"
              >
                Open on Localhost:3000
              </button>
              <button
                type="button"
                onClick={() => setShowHelpModal(false)}
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
