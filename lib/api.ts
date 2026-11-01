import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '', 
  timeout: 60000,
});

// Automatic authorization header interceptor for authenticated Citizen/Proctor/Committee sessions
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = 
      localStorage.getItem('nyaypath_citizen_token') ||
      localStorage.getItem('nyaypath_lawyer_token') ||
      localStorage.getItem('nyaypath_token') ||
      localStorage.getItem('nyaypath_proctor_token');
    if (token && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
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

// =====================================================================
// College Proctorial & Student Grievance Redressal API (RBAC Secured)
// =====================================================================

export const loginProctor = (payload: {
  email?: string;
  password?: string;
  institution_id?: string;
  access_key?: string;
  role?: string;
}) => api.post('/api/campus-proctor/auth/login', payload).then(r => r.data)

export const submitCampusGrievance = (payload: any) =>
  api.post('/api/campus-proctor/submit', payload).then(r => r.data)

export const trackCampusGrievance = (case_id: string, verification_key: string) =>
  api.post('/api/campus-proctor/track', { case_id, verification_key }).then(r => r.data)

export const getCampusCase = (case_id: string, verification_key?: string) => {
  const url = verification_key 
    ? `/api/campus-proctor/case/${case_id}?verification_key=${encodeURIComponent(verification_key)}`
    : `/api/campus-proctor/case/${case_id}`;
  return api.get(url).then(r => r.data)
}

export const listCampusCases = () =>
  api.get('/api/campus-proctor/cases').then(r => r.data)

export const updateCampusCase = (payload: any) =>
  api.post('/api/campus-proctor/update', payload).then(r => r.data)

export const getProctorNotice = (case_id: string, verification_key?: string) => {
  const url = verification_key
    ? `/api/campus-proctor/notice/${case_id}?verification_key=${encodeURIComponent(verification_key)}`
    : `/api/campus-proctor/notice/${case_id}`;
  return api.get(url).then(r => r.data)
}

// =====================================================================
// Citizen Dashboard & My Cases Workspace API (Phase 2.1)
// =====================================================================

export const loginCitizen = (payload: { email: string; password?: string }) =>
  api.post('/api/citizen/auth/login', payload).then(r => r.data)

export const getCitizenDashboardStats = () =>
  api.get('/api/citizen/dashboard-stats').then(r => r.data)

export const getCitizenCases = (params?: {
  status?: string;
  category?: string;
  search?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  limit?: number;
}) => {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'ALL') query.set('status', params.status);
  if (params?.category && params.category !== 'ALL') query.set('category', params.category);
  if (params?.search) query.set('search', params.search);
  if (params?.sort_by) query.set('sort_by', params.sort_by);
  if (params?.sort_order) query.set('sort_order', params.sort_order);
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));

  const qs = query.toString();
  return api.get(`/api/citizen/cases${qs ? `?${qs}` : ''}`).then(r => r.data);
}

export const getCitizenCaseDetails = (case_id: string) =>
  api.get(`/api/citizen/cases/${encodeURIComponent(case_id)}`).then(r => r.data)

export const getCaseDocumentUrl = (case_id: string, document_id: string, verification_key?: string) => {
  const url = verification_key
    ? `/api/campus-proctor/document-url?case_id=${encodeURIComponent(case_id)}&document_id=${encodeURIComponent(document_id)}&verification_key=${encodeURIComponent(verification_key)}`
    : `/api/campus-proctor/document-url?case_id=${encodeURIComponent(case_id)}&document_id=${encodeURIComponent(document_id)}`;
  return api.get(url).then(r => r.data)
}

// =====================================================================
// Central Case Management & Filing System API (Phase 2.2)
// =====================================================================

export interface CaseFilingPayload {
  category: string;
  sub_category?: string;
  subject: string;
  facts: string;
  remedy_sought?: string;
  department?: string;
  incident_date?: string;
  is_confidential?: boolean;
  supporting_documents?: Array<{
    document_id?: string;
    file_name: string;
    storage_path: string;
    file_size_bytes?: number;
    mime_type?: string;
  }>;
  declaration_confirmed: boolean;
}

export const fileCitizenCase = (payload: CaseFilingPayload) =>
  api.post('/api/citizen/cases/file', payload).then(r => r.data);

export const uploadCaseDocument = (file: File, caseId?: string) => {
  const formData = new FormData();
  formData.append('file', file);
  if (caseId) formData.append('case_id', caseId);
  return api.post('/api/citizen/cases/upload-document', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }).then(r => r.data);
};

export const executeCaseLifecycleAction = (
  caseId: string,
  payload: { action: string; remarks?: string; reason?: string }
) =>
  api.post(`/api/citizen/cases/${encodeURIComponent(caseId)}/lifecycle`, payload).then(r => r.data);

export const trackCitizenCase = (caseId: string, verificationKey?: string) => {
  const url = verificationKey
    ? `/api/citizen/track/${encodeURIComponent(caseId)}?verification_key=${encodeURIComponent(verificationKey)}`
    : `/api/citizen/track/${encodeURIComponent(caseId)}`;
  return api.get(url).then(r => r.data);
};

// =====================================================================
// Intelligent In-App Notification System API (Phase 2.3)
// =====================================================================

export interface CaseNotification {
  id: string;
  recipient_user_id: string;
  event_type: string;
  title: string;
  message: string;
  related_case_id: string;
  case_uuid?: string;
  is_read: boolean;
  action_url?: string;
  created_at: string;
  read_at?: string;
  metadata?: Record<string, any>;
}

export const getUserNotifications = (params?: { is_read?: boolean; limit?: number; offset?: number }) => {
  const query = new URLSearchParams();
  if (params?.is_read !== undefined) query.set('is_read', String(params.is_read));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  return api.get(`/api/notifications${qs ? `?${qs}` : ''}`).then(r => r.data);
};

export const getUnreadNotificationCount = () =>
  api.get('/api/notifications/unread-count').then(r => r.data);

export const markNotificationAsRead = (notificationId: string) =>
  api.post(`/api/notifications/${encodeURIComponent(notificationId)}/read`).then(r => r.data);

export const markAllNotificationsAsRead = () =>
  api.post('/api/notifications/mark-all-read').then(r => r.data);

export const deleteNotification = (notificationId: string) =>
  api.delete(`/api/notifications/${encodeURIComponent(notificationId)}`).then(r => r.data);

// =====================================================================
// Legal Citations Resolution API (Phase 2.3)
// =====================================================================

export interface CitationMetadata {
  source_identifier: string;
  case_title: string;
  court: string;
  citation: string;
  year?: number;
  authority_type: 'BINDING' | 'PERSUASIVE';
  bench?: string;
  category: string;
  statutory_provisions: string[];
  relevant_ratio: string;
  how_to_cite: string;
  source_url?: string;
  pdf_download_url?: string;
  is_verified: boolean;
}

export const resolveLegalCitations = (query: string, maxResults: number = 3) =>
  api.post('/api/citations/resolve', { query, max_results: maxResults }).then(r => r.data);

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

// =====================================================================
// Multi-Institution & Proctor Workspace API (Phase 4)
// =====================================================================

export interface InstitutionStats {
  institution_id: string;
  total_cases: number;
  active_inquiries: number;
  resolved_cases: number;
  hearings_scheduled: number;
  confidential_cases: number;
  sla_breaches: number;
  total_members: number;
  active_members: number;
  unassigned_cases: number;
}

export interface InstitutionAnalytics {
  institution_id: string;
  total_cases: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  avg_resolution_days: number;
  resolved_count: number;
}

export interface InstitutionMember {
  id: string;
  user_id: string;
  institution_code: string;
  role: string;
  department?: string;
  designation?: string;
  account_status: 'active' | 'suspended' | 'revoked';
  full_name?: string;
  email?: string;
  created_at: string;
}

export interface CommitteeObservationPayload {
  case_id: string;
  observations: string;
  recommendations?: string;
  findings?: string;
}

export const getInstitutionDashboardStats = () =>
  api.get('/api/institution/dashboard-stats').then(r => r.data);

export const getInstitutionAnalytics = () =>
  api.get('/api/institution/analytics').then(r => r.data);

export const getInstitutionCases = (params?: {
  status?: string;
  category?: string;
  severity?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) => {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.category) query.set('category', params.category);
  if (params?.severity) query.set('severity', params.severity);
  if (params?.search) query.set('search', params.search);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  return api.get(`/api/institution/cases${qs ? `?${qs}` : ''}`).then(r => r.data);
};

export const getInstitutionMembers = () =>
  api.get('/api/institution/members').then(r => r.data);

export const updateInstitutionMemberStatus = (userId: string, accountStatus: string) =>
  api.patch(`/api/institution/members/${encodeURIComponent(userId)}/status`, { account_status: accountStatus }).then(r => r.data);

export const getInstitutionCommitteeRoster = () =>
  api.get('/api/institution/committee-roster').then(r => r.data);

export const getChiefTriageQueue = () =>
  api.get('/api/campus-proctor/chief/triage').then(r => r.data);

export const getProctorMyCases = () =>
  api.get('/api/campus-proctor/my-cases').then(r => r.data);

export const getCommitteeInquiries = () =>
  api.get('/api/campus-proctor/committee/my-inquiries').then(r => r.data);

export const assignCaseCommitteeMember = (payload: {
  case_id: string;
  target_user_id: string;
  role?: string;
  committee_name?: string;
}) => api.post('/api/campus-proctor/committee/assign', payload).then(r => r.data);

export const revokeCaseCommitteeMember = (payload: {
  case_id: string;
  target_user_id: string;
}) => api.post('/api/campus-proctor/committee/revoke', payload).then(r => r.data);

export const getCaseCommitteeAssignments = (caseId: string) =>
  api.get(`/api/campus-proctor/committee/assignments/${encodeURIComponent(caseId)}`).then(r => r.data);

export const submitCommitteeObservations = (payload: CommitteeObservationPayload) =>
  api.post('/api/campus-proctor/committee/observations', payload).then(r => r.data);

// =====================================================================
// Lawyer Connect & Client Workspace API (Phase 5)
// =====================================================================

export interface LawyerProfile {
  id: string;
  user_id?: string;
  lawyer_user_id?: string;
  full_name: string;
  email: string;
  phone?: string;
  bar_council: string;
  enrollment_state: string;
  enrollment_number?: string;
  years_of_practice: number;
  specializations: string[];
  courts: string[];
  languages: string[];
  bio?: string;
  consultation_preferences?: {
    modes?: string[];
    consultation_fee?: string;
  };
  photo_url?: string;
  verification_status: 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED';
  created_at: string;
}

export interface ConsultationRequest {
  id: string;
  citizen_user_id: string;
  lawyer_user_id: string;
  case_id?: string;
  case_uuid?: string;
  legal_issue: string;
  description: string;
  preferred_mode: 'ONLINE' | 'IN_PERSON' | 'PHONE';
  status: 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN' | 'COMPLETED';
  lawyer_response?: string;
  response_date?: string;
  created_at: string;
  updated_at: string;
  lawyer?: Partial<LawyerProfile>;
  client?: { full_name?: string; email?: string };
}

export interface LawyerDashboardStats {
  lawyer_user_id: string;
  total_requests: number;
  pending_requests: number;
  accepted_consultations: number;
  completed_consultations: number;
  active_clients: number;
  shared_cases: number;
}

export const registerLawyer = (payload: {
  full_name: string;
  phone?: string;
  bar_council: string;
  enrollment_state: string;
  enrollment_number: string;
  years_of_practice?: number;
  specializations?: string[];
  courts?: string[];
  languages?: string[];
  bio?: string;
  consultation_preferences?: Record<string, any>;
  photo_url?: string;
}) => api.post('/api/lawyer/register', payload).then(r => r.data);

export const getVerifiedLawyers = (params?: {
  specialization?: string;
  state?: string;
  court?: string;
  language?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) => {
  const query = new URLSearchParams();
  if (params?.specialization) query.set('specialization', params.specialization);
  if (params?.state) query.set('state', params.state);
  if (params?.court) query.set('court', params.court);
  if (params?.language) query.set('language', params.language);
  if (params?.search) query.set('search', params.search);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  return api.get(`/api/lawyers${qs ? `?${qs}` : ''}`).then(r => r.data);
};

export const getLawyerProfile = (lawyerId: string) =>
  api.get(`/api/lawyers/${encodeURIComponent(lawyerId)}`).then(r => r.data);

export const updateLawyerProfile = (payload: Partial<LawyerProfile>) =>
  api.patch('/api/lawyer/profile', payload).then(r => r.data);

export const verifyLawyer = (lawyerId: string, decision: 'VERIFIED' | 'REJECTED' | 'SUSPENDED', notes?: string) =>
  api.post(`/api/admin/lawyers/${encodeURIComponent(lawyerId)}/verify`, { decision, notes }).then(r => r.data);

export const requestConsultation = (payload: {
  lawyer_user_id: string;
  case_id?: string;
  legal_issue: string;
  description: string;
  preferred_mode?: string;
}) => api.post('/api/consultations/request', payload).then(r => r.data);

export const getCitizenConsultations = () =>
  api.get('/api/citizen/consultations').then(r => r.data);

export const getLawyerConsultations = (status?: string) => {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return api.get(`/api/lawyer/consultations${qs}`).then(r => r.data);
};

export const updateConsultationStatus = (requestId: string, payload: { status: string; lawyer_response?: string }) =>
  api.patch(`/api/consultations/${encodeURIComponent(requestId)}/status`, payload).then(r => r.data);

export const shareCaseWithLawyer = (payload: {
  case_id: string;
  lawyer_user_id: string;
  shared_scope?: string;
  consultation_request_id?: string;
}) => api.post('/api/citizen/cases/share', payload).then(r => r.data);

export const revokeLawyerCaseAccess = (payload: {
  case_id: string;
  lawyer_user_id: string;
}) => api.post('/api/citizen/cases/revoke-share', payload).then(r => r.data);

export const getLawyerSharedCases = () =>
  api.get('/api/lawyer/shared-cases').then(r => r.data);

export const getLawyerDashboardStats = () =>
  api.get('/api/lawyer/dashboard-stats').then(r => r.data);


