'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import useCaseStore from '@/store/caseStore';
import GatewayView from '@/views/GatewayView';
import IntakeFormView from '@/views/IntakeFormView';
import RTIResultView from '@/views/RTIResultView';
import GrievanceResultView from '@/views/GrievanceResultView';
import OutOfScopeView from '@/views/OutOfScopeView';

export default function DashboardApp() {
  const { stage, userProblem, setUserProblem } = useCaseStore() as any;

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const savedProblem = sessionStorage.getItem('nyaypath_problem') || sessionStorage.getItem('janadhikar_problem');
    if (savedProblem && !userProblem) {
      setUserProblem(savedProblem);
      sessionStorage.removeItem('nyaypath_problem');
      sessionStorage.removeItem('janadhikar_problem');
    }
  }, [userProblem, setUserProblem]);

  if (stage === 'IDLE' || stage === 'INITIALIZING') {
    return <GatewayView />;
  }
  if (stage === 'CLASSIFYING' || stage === 'RTI_GATHERING' || stage === 'GRIEVANCE_GATHERING') {
    return <IntakeFormView />;
  }
  if (stage === 'PREDICTING' || stage === 'IMPROVING' || stage === 'RTI_PREDICTED' || stage === 'RTI_COMPLETED') {
    return <RTIResultView />;
  }
  if (stage === 'COMPLETE' || stage === 'GRIEVANCE_COMPLETED' || stage === 'GRIEVANCE_ANALYZING') {
    return <GrievanceResultView />;
  }
  if (stage === 'OUT_OF_SCOPE') return <OutOfScopeView />;

  return <GatewayView />;
}
