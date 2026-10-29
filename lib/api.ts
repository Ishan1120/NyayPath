import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '', 
  timeout: 60000,
});

export const initCase = () => api.post('/api/case/init').then(r => r.data)
export const classifyCase = (case_id: string, problem_text: string, language: string) => api.post('/api/case/classify', { case_id, problem_text, language }).then(r => r.data)
export const rtiGenerate = (case_id: string, form_data: any) => api.post('/api/rti/generate', { case_id, form_data }).then(r => r.data)
export const resolveDepartment = (case_id: string, location: string | null = null) => api.post('/api/rti/resolve-department', { case_id, location }).then(r => r.data)
export const downloadRtiPdf = (case_id: string) => api.get(`/api/rti/pdf/${case_id}`, { responseType: 'blob' }).then(r => r.data)
export const rtiPredict = (case_id: string, draft_text: string | null = null) => api.post('/api/rti/predict', { case_id, draft_text }).then(r => r.data)
export const rtiImprove = (case_id: string) => api.post('/api/rti/improve', { case_id }).then(r => r.data)

// Point directly to the python backend to bypass Next.js API wrapper issues
export const analyzePio = (case_id: string, pio_text: string) => api.post('/api/analyze_pio_backend', { case_id, pio_text }).then(r => r.data)

// Watchdog & SLA Engine API
export const startWatchdog = (case_id: string, life_liberty: boolean = false) =>
  api.post('/api/watchdog/start', { case_id, life_liberty }).then(r => r.data)

export const getWatchdogState = (case_id: string) =>
  api.get(`/api/watchdog/${case_id}`).then(r => r.data)

export const recordWatchdogResponse = (case_id: string, pio_text: string, response_received_at?: string) =>
  api.post('/api/watchdog/response', { case_id, pio_text, response_received_at }).then(r => r.data)

export const simulateWatchdog = (case_id: string, scenario: string, simulated_days_ago?: number) =>
  api.post('/api/watchdog/simulate', { case_id, scenario, simulated_days_ago }).then(r => r.data)

// Translate API
export const translateDocument = (text: string, target_language: string) => api.post('/api/translate', { text, target_language }).then(r => r.data)

export const transcribeAudio = (audioBlob: Blob, language: string) => {
  const formData = new FormData()
  const extension = audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
  formData.append('audio_file', audioBlob, `recording.${extension}`)
  formData.append('language', language || 'English')
  return api.post('/api/transcribe', formData).then(r => r.data)
}

export const downloadGenericPdf = (title: string, content: string) => {
  return api.post('/api/generate-pdf', { title, content }, { responseType: 'blob' })
    .then(r => r.data)
}

export const grievanceGenerate = (payload: any) => {
  return api.post('/api/grievance/generate', payload).then(r => r.data)
}

export const getCase = (case_id: string) => api.get(`/api/case/${case_id}`).then(r => r.data)

export const intakeChat = (payload: any) => api.post('/api/intake/chat', payload).then(r => r.data)

// Interactive AI Clarifying Questions & Systematic Legal Draft Engine
export const getClarifyingQuestions = (problem_text: string, language: string = 'English') =>
  api.post('/api/intake/clarifying-questions', { problem_text, language }).then(r => r.data)

export const synthesizeDraft = (payload: {
  case_id?: string;
  problem_text: string;
  answers: Record<string, string>;
  language?: string;
  route?: string;
  applicant_name?: string;
}) => api.post('/api/intake/synthesize-draft', payload).then(r => r.data)

// Social Media Campaign Generator (GraphRAG-powered)
export const generateSocialCampaign = (
  case_id: string,
  user_problem: string,
  language: string,
  form_data?: any
) => api.post('/api/social/generate', { case_id, user_problem, language, form_data }).then(r => r.data)

// Live Court News & Legal Updates API
export const fetchCourtNews = (category: string = 'All', refresh: boolean = false) =>
  api.get(`/api/court-news?category=${encodeURIComponent(category)}${refresh ? '&refresh=true' : ''}`).then(r => r.data)

// Precedent Library & AI Case Summarizer API
export const searchPrecedents = (query: string = '', category: string = 'All') =>
  api.post('/api/precedents/search', { query, category }).then(r => r.data)

export const summarizePrecedent = (case_id?: string, custom_text?: string, language: string = 'English', user_problem?: string) =>
  api.post('/api/precedents/summarize', { case_id, custom_text, language, user_problem }).then(r => r.data)

export const downloadCaseBriefPdf = (case_id: string) =>
  api.get(`/api/precedents/${case_id}/pdf`, { responseType: 'blob' }).then(r => r.data)

// College Proctorial & Student Grievance Redressal API
export const submitCampusGrievance = (payload: any) =>
  api.post('/api/campus-proctor/submit', payload).then(r => r.data)

export const getCampusCase = (case_id: string) =>
  api.get(`/api/campus-proctor/case/${case_id}`).then(r => r.data)

export const listCampusCases = () =>
  api.get('/api/campus-proctor/cases').then(r => r.data)

export const updateCampusCase = (payload: any) =>
  api.post('/api/campus-proctor/update', payload).then(r => r.data)

export const getProctorNotice = (case_id: string) =>
  api.get(`/api/campus-proctor/notice/${case_id}`).then(r => r.data)

export default api

export const triggerBlobDownload = (blobData: Blob, filename: string) => {
  const url = window.URL.createObjectURL(new Blob([blobData]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
};
