from processing_quality_agent.models.diagnosis import Diagnosis
from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import QualityAssessment
from processing_quality_agent.skills.failure_diagnosis import diagnose


class DiagnosisService:
    def diagnose(self, context: DocumentContext, assessment: QualityAssessment) -> Diagnosis:
        return diagnose(context, assessment)
