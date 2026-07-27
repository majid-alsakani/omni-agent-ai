from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class MemoryEntry(BaseModel):
    """مدخل واحد في الذاكرة"""
    id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    importance: float = 0.0  # من 0 إلى 1 لتحديد أهمية المعلومة

class EpisodicMemory(BaseModel):
    """الذاكرة العرضية: تخزن أحداث الجلسة الحالية"""
    session_id: str
    events: List[MemoryEntry] = []
    
    def add_event(self, content: str, importance: float = 0.5):
        entry = MemoryEntry(id=f"evt_{len(self.events)}", content=content, importance=importance)
        self.events.append(entry)
        # الحفاظ على آخر 50 حدث فقط لتقليل الضجيج
        if len(self.events) > 50:
            self.events.pop(0)

class SemanticMemory(BaseModel):
    """الذاكرة الدلالية: تخزن الحقائق الدائمة (تحتاج لقاعدة بيانات Vector)"""
    user_id: str
    facts: List[MemoryEntry] = []
    
    # في الواقع، هذه الفئة ستتصل بـ ChromaDB أو Pinecone
    def query_facts(self, query: str, top_k: int = 3):
        """البحث عن الحقائق المتعلقة بالاستفسار"""
        # هنا يتم تنفيذ Vector Search
        return self.facts[:top_k]

class ProceduralMemory(BaseModel):
    """الذاكرة الإجرائية: تخزن كيفية تنفيذ المهام (Prompts/Skills)"""
    skills: dict = {
        "market_analysis": "خطوات تحليل السوق: 1. جمع البيانات 2. المقارنة 3. التقرير",
        "code_review": "خطوات مراجعة الكود: 1. الأمان 2. الكفاءة 3. التوثيق"
    }

class OmniMemorySystem:
    """النظام المتكامل لذاكرة أومني"""
    def __init__(self, user_id: str, session_id: str):
        self.episodic = EpisodicMemory(session_id=session_id)
        self.semantic = SemanticMemory(user_id=user_id)
        self.procedural = ProceduralMemory()
        
    def get_context(self, current_query: str) -> str:
        """تجميع السياق من كل أنواع الذاكرة لتقديمه للـ LLM"""
        recent_events = "\n".join([e.content for e in self.episodic.events[-5:]])
        relevant_facts = "\n".join([f.content for f in self.semantic.query_facts(current_query)])
        
        context = f"""
        [الذاكرة العرضية - الأحداث الأخيرة]:
        {recent_events}
        
        [الذاكرة الدلالية - الحقائق ذات الصلة]:
        {relevant_facts}
        """
        return context
