'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Mic, Send, FileText } from 'lucide-react';
import { initCase, classifyCase, rtiGenerate, transcribeAudio } from '@/lib/api';

export default function RTIIntakePage() {
  const router = useRouter();
  const [problemText, setProblemText] = useState('');
  const [language, setLanguage] = useState('en');
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);

  const handleSubmit = async (textToSubmit: string) => {
    if (!textToSubmit.trim()) return;

    setLoading(true);
    try {
      const initRes = await initCase();
      const caseId = initRes.case_id;

      await classifyCase(caseId, textToSubmit, language);
      await rtiGenerate(caseId, { problem_text: textToSubmit });

      router.push(`/rti/result?case_id=${caseId}`);
    } catch (err) {
      console.error('Failed to initialize or generate RTI:', err);
      alert('An error occurred. Please check your connection and try again.');
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];

      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        setLoading(true);
        try {
          const transcriptionRes = await transcribeAudio(audioBlob, language);
          const transcribedText = transcriptionRes.text || transcriptionRes.transcription;
          if (transcribedText) {
            setProblemText(transcribedText);
            await handleSubmit(transcribedText);
          } else {
            setLoading(false);
            alert('Could not transcribe audio. Please type your issue.');
          }
        } catch (err) {
          console.error('Transcription failed:', err);
          setLoading(false);
          alert('Audio transcription failed.');
        }
      };

      recorder.start();
      setMediaRecorder(recorder);
      setRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('Microphone permission is required for voice intake.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder) {
      mediaRecorder.stop();
      setRecording(false);
    }
  };

  return (
    <main 
      className="min-h-screen py-12 px-4 sm:px-6 flex items-center justify-center bg-cover bg-center bg-no-repeat relative text-slate-200"
      style={{ backgroundImage: "url('/bg.image.png')" }}
    >
      <div className="max-w-2xl w-full space-y-6 relative z-10">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center p-3 bg-white/95 text-court-maroon rounded-2xl mb-2 shadow-sm border border-slate-300">
            <FileText size={24} />
          </div>
          <h1 className="text-2xl font-extrabold text-white drop-shadow-sm tracking-tight">File an RTI Application</h1>
          <p className="text-xs text-slate-200 font-medium drop-shadow-sm">
            Describe your grievance or information request below, or use voice input.
          </p>
        </div>

        <div className="bg-white/95 backdrop-blur-sm border border-slate-300 rounded-3xl p-6 sm:p-8 shadow-xl space-y-4">
          <div>
            <label className="block text-xs font-bold text-ashoka-navy uppercase tracking-wider mb-2">
              Select Language
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full p-3 text-xs bg-[#F8FAFC] border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#FF9933] text-ashoka-navy font-medium"
            >
              <option value="en">English</option>
              <option value="hi">Hindi (हिन्दी)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-ashoka-navy uppercase tracking-wider mb-2">
              Describe Your Issue / Information Request
            </label>
            <textarea
              value={problemText}
              onChange={(e) => setProblemText(e.target.value)}
              placeholder="E.G., I applied for my passport 3 months ago at the regional office, but haven't received any updates..."
              rows={6}
              className="w-full p-4 text-xs font-mono bg-[#F8FAFC] border border-slate-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#FF9933] leading-relaxed text-ashoka-navy placeholder-slate-400"
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => handleSubmit(problemText)}
              disabled={loading || !problemText.trim()}
              type="button"
              className="flex-1 flex items-center justify-center gap-2 py-3 text-xs font-bold text-white bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 transition-colors rounded-xl shadow-md disabled:opacity-50 cursor-pointer tracking-tight font-sans"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {loading ? 'Processing Application...' : 'Generate RTI Application'}
            </button>

            <button
              onClick={recording ? stopRecording : startRecording}
              disabled={loading}
              type="button"
              className={`flex items-center justify-center px-4 py-3 text-xs font-bold rounded-xl border transition-colors cursor-pointer tracking-tight font-sans ${
                recording
                  ? 'bg-rose-50 text-court-maroon border-rose-200 animate-pulse'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
              }`}
            >
              <Mic size={16} />
              <span className="ml-1.5">{recording ? 'Stop' : 'Voice'}</span>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
