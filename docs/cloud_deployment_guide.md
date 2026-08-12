# دليل النشر السحابي لـ Omni-Agent AI مع PostgreSQL و pgvector

يوضح هذا الدليل الخطوات العملية لنشر النظام على خادم سحابي حقيقي (مثل AWS RDS، Supabase، Render، أو خادم VPS خاص) مع تفعيل الذاكرة المتجهية الدائمة.

---

## 1. إعداد قاعدة البيانات السحابية (PostgreSQL + pgvector)

تتطلب الذاكرة الدلالية السيادية قاعدة بيانات تدعم فهرسة المتجهات (Vector Indexing). يمكنك استخدام أي خدمة PostgreSQL سحابية تدعم امتداد `pgvector` (مثل Supabase أو Neon أو AWS RDS مع PostgreSQL 15+).

### أ. تفعيل الامتداد وإنشاء الجدول
قم بالاتصال بقاعدة البيانات السحابية وتنفيذ الأمر التالي:

```sql
-- تفعيل امتداد المتجهات
CREATE EXTENSION IF NOT EXISTS vector;

-- إنشاء جدول الذاكرة الدلالية السيادية
CREATE TABLE IF NOT EXISTS omni_semantic_memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(64) NOT NULL, -- يمكن تعديل الأبعاد حسب نموذج التضمين (مثلاً 1536 لـ OpenAI)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- إنشاء فهرس الأداء العالي للبحث السريع (IVFFlat أو HNSW)
CREATE INDEX IF NOT EXISTS omni_semantic_memory_user_idx 
ON omni_semantic_memory(user_id);
```

---

## 2. إعداد بيئة التشغيل السحابية (Environment Configuration)

على خادم النشر (مثل Docker، Render، أو AWS EC2)، قم بتعريف متغيرات البيئة التالية:

```bash
# رابط الاتصال بقاعدة البيانات السحابية (مثلاً من Supabase أو RDS)
export OMNI_VECTOR_DSN='postgresql://postgres:YOUR_PASSWORD@db.region.supabase.co:5432/postgres?sslmode=require'

# منع التراجع للوضع المحلي عند انقطاع الاتصال (اختياري للإنتاج الصارم)
export ALLOW_LOCAL_VECTOR_FALLBACK=0

# مفتاح نموذج اللغة (إذا كنت تستخدم مزوداً حقيقياً)
export OPENAI_API_KEY='sk-...'
```

---

## 3. التشغيل عبر Docker في الإنتاج

يمكنك نشر النظام باستخدام ملف `Dockerfile` المرفق في المشروع:

```bash
# بناء الصورة
docker build -t omni-agent-ai:v3 .

# تشغيل الحاوية مع ربط متغيرات البيئة السحابية
docker run -d \
  --name omni-agent-prod \
  -p 8000:8000 \
  -e OMNI_VECTOR_DSN='postgresql://postgres:YOUR_PASSWORD@your-cloud-db.com:5432/postgres?sslmode=require' \
  -e ALLOW_LOCAL_VECTOR_FALLBACK=0 \
  omni-agent-ai:v3
```

---

## 4. التحقق من سلامة النشر السحابي

بعد إقلاع الخادم، قم بفحص نقطة الصحة (Health Check) للتأكد من أن الذاكرة متصلة بالسحابة بنجاح:

```bash
curl https://your-cloud-domain.com/health
```

النتيجة المتوقعة:
```json
{
  "status": "ok",
  "memory_records": 125,
  "engines": ["langgraph-single", "langgraph-multi-agent"],
  "vector_store": "postgres-pgvector"
}
```
إذا ظهرت قيمة `vector_store` كـ `postgres-pgvector`، فهذا يعني أن نظامك متصل بالكامل بقاعدة البيانات السحابية المتجهية.

---

## 5. ملاحظات الأداء والأمان

يجب مطابقة أبعاد عمود `vector(n)` مع نموذج الـ embeddings المستخدم فعلياً، وإعادة فهرسة البيانات عند تغيير النموذج. وللبيئات متعددة المستخدمين، يجب أن يكون `user_id` أو `tenant_id` جزءاً من شرط الاستعلام والفهرس المنطقي. عند استخدام HNSW أو IVFFlat مع مرشحات إضافية، اختبر عدد النتائج الفعلي لأن الفهرس التقريبي قد يعيد نتائج أقل من الحد المطلوب دون إعداد iterative search مناسب [1] [2].

لا تضع بيانات الاعتماد في المستودع. استخدم Secrets أو متغيرات بيئة محمية، وفعّل TLS (`sslmode=require`) ومبدأ أقل صلاحية. لا تجعل `ALLOW_LOCAL_VECTOR_FALLBACK=1` في الإنتاج الصارم إذا كان فقدان اتصال قاعدة البيانات يجب أن يفشل الخدمة بدلاً من العمل على ذاكرة محلية.

## References

[1]: https://github.com/pgvector/pgvector "pgvector الرسمي: بحث التشابه والفهارس في PostgreSQL"
[2]: https://supabase.com/docs/guides/database/extensions/pgvector "Supabase Docs: pgvector embeddings and vector similarity"
