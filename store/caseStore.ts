import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface CaseState {
  stage: string;
  setStage: (stage: string) => void;
  language: string;
  setLanguage: (language: string) => void;
  caseId: string | null;
  setCaseId: (caseId: string | null) => void;
  userProblem: string;
  setUserProblem: (userProblem: string) => void;
  classifyResult: any;
  setClassifyResult: (classifyResult: any) => void;
  triageConfirmed: boolean;
  setTriageConfirmed: (triageConfirmed: boolean) => void;
  formData: Record<string, any>;
  setFormData: (formData: Record<string, any>) => void;
  departmentInfo: any;
  setDepartmentInfo: (departmentInfo: any) => void;
  departmentConfirmed: boolean;
  setDepartmentConfirmed: (v: boolean) => void;
  rtiPrediction: any;
  setRtiPrediction: (rtiPrediction: any) => void;
  rtiDraft: string | null;
  setRtiDraft: (rtiDraft: string | null) => void;
  grievanceResult: any;
  setGrievanceResult: (grievanceResult: any) => void;
  watchdogState: any;
  setWatchdogState: (watchdogState: any) => void;
  clarifyingQuestions?: any;
  setClarifyingQuestions: (q: any) => void;
  clarifyingAnswers?: Record<string, string>;
  setClarifyingAnswers: (answers: Record<string, string>) => void;
  lawyerBrief?: string | null;
  setLawyerBrief: (brief: string | null) => void;
  citedPrecedents: Array<{
    id: string;
    title: string;
    citation: string;
    how_to_cite: string;
    ratio: string;
    court: string;
  }>;
  addPrecedentCitation: (precedent: any) => void;
  removePrecedentCitation: (id: string) => void;
  error: string | null;
  setError: (error: string | null) => void;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  hydrateState: (caseId: string, backendData: any) => void;
  reset: () => void;
  
  [key: string]: any; 
}

const useCaseStore = create<CaseState>()(
  persist(
    (set, get) => ({
      stage: 'IDLE',
      setStage: (stage) => set({ stage }),
      language: 'English',
      setLanguage: (language) => set({ language }),
      caseId: null,
      setCaseId: (caseId) => set({ caseId }),
      userProblem: '',
      setUserProblem: (userProblem) => set({ userProblem }),
      classifyResult: null,
      setClassifyResult: (classifyResult) => set({ classifyResult }),
      triageConfirmed: false,
      setTriageConfirmed: (triageConfirmed) => set({ triageConfirmed }),
      formData: {},
      setFormData: (formData) => set({ formData }),
      departmentInfo: null,
      setDepartmentInfo: (departmentInfo) => set({ departmentInfo }),
      departmentConfirmed: false,
      setDepartmentConfirmed: (v) => set({ departmentConfirmed: v }),
      rtiPrediction: null,
      setRtiPrediction: (rtiPrediction) => set({ rtiPrediction }),
      rtiDraft: null,
      setRtiDraft: (rtiDraft) => set({ rtiDraft }),
      grievanceResult: null,
      setGrievanceResult: (grievanceResult) => set({ grievanceResult }),
      watchdogState: null,
      setWatchdogState: (watchdogState) => set({ watchdogState }),
      clarifyingQuestions: null,
      setClarifyingQuestions: (clarifyingQuestions) => set({ clarifyingQuestions }),
      clarifyingAnswers: {},
      setClarifyingAnswers: (clarifyingAnswers) => set({ clarifyingAnswers }),
      lawyerBrief: null,
      setLawyerBrief: (lawyerBrief) => set({ lawyerBrief }),
      socialCampaign: null,
      setSocialCampaign: (socialCampaign: any) => set({ socialCampaign }),
      citedPrecedents: [],
      addPrecedentCitation: (p) => set((state) => {
        const existing = state.citedPrecedents || [];
        if (existing.some((c) => c.id === p.id)) return state;
        return {
          citedPrecedents: [
            ...existing,
            {
              id: p.id,
              title: p.title,
              citation: p.citation,
              how_to_cite: p.how_to_cite,
              ratio: p.key_ratio || p.ratio || "",
              court: p.court,
            }
          ]
        };
      }),
      removePrecedentCitation: (id) => set((state) => ({
        citedPrecedents: (state.citedPrecedents || []).filter((c) => c.id !== id)
      })),
      error: null,
      setError: (error) => set({ error }),
      isLoading: false,
      setIsLoading: (isLoading) => set({ isLoading }),

      hydrateState: (caseId, backendData) => {
        const route = backendData.route;
        let newStage = 'IDLE';

        if (backendData.status === 'classified') {
          newStage = route === 'RTI' ? 'RTI_GATHERING' : 'GRIEVANCE_GATHERING';
        } else if (backendData.status === 'rti_drafted') {
          newStage = 'PREDICTING';
        } else if (backendData.status === 'rti_predicted') {
          newStage = 'IMPROVING';
        } else if (backendData.status === 'rti_completed' || backendData.status === 'grievance_completed') {
          newStage = 'COMPLETE';
        }

        set((state) => ({
          caseId: caseId,
          language: backendData.language || state.language || 'English',
          userProblem: backendData.user_problem || state.userProblem || '',
          classifyResult: backendData.route ? {
            route: backendData.route,
            sub_category: backendData.sub_category,
            form_schema: backendData.form_schema || [],
            reasoning: "Resumed from saved passkey."
          } : state.classifyResult,
          triageConfirmed: !!backendData.route,
          formData: backendData.form_data || state.formData || {},
          departmentInfo: backendData.department_info || null,
          departmentConfirmed: !!backendData.department_info,
          rtiPrediction: backendData.prediction_result || null,
          rtiDraft: backendData.improved_draft || backendData.initial_draft || null,
          grievanceResult: backendData.grievance_pack || null,
          watchdogState: backendData.watchdog_status ? backendData : state.watchdogState,
          stage: newStage !== 'IDLE' ? newStage : state.stage,
        }));
      },

      reset: () =>
        set({
          stage: 'IDLE',
          caseId: null,
          userProblem: '',
          classifyResult: null,
          triageConfirmed: false,
          formData: {},
          departmentInfo: null,
          departmentConfirmed: false,
          rtiPrediction: null,
          rtiDraft: null,
          grievanceResult: null,
          watchdogState: null,
          socialCampaign: null,
          citedPrecedents: [],
          error: null,
          isLoading: false,
        }),
    }),
    {
      name: 'nyaypath_case_storage',
      storage: createJSONStorage(() => (typeof window !== 'undefined' ? localStorage : {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {}
      })),
    }
  )
)

export default useCaseStore;
