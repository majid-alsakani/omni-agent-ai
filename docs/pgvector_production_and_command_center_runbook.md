# دليل التشغيل الإنتاجي: PostgreSQL/pgvector وOmni-Agent Command Center

## الهدف والنطاق

يوضح هذا الدليل ربط **Omni-Agent 3.3** بقاعدة PostgreSQL تدعم امتداد `pgvector` حتى تبقى **الذاكرة الدلالية** للتوأم الاستراتيجي بعد إعادة تشغيل التطبيق أو إعادة نشره. كما يوضح تشغيل واجهة **Command Center** محلياً واستعراض تقرير مبيعات من ملف CSV.

> الذاكرة الدلالية تحفظ الحقائق والقرارات المعتمدة القابلة للاسترجاع. أما الذاكرة العرضية ومسودات التوأم فتُحفظ حالياً في `data/memory.json` و`data/strategic_twin_drafts.json`. في بيئة إنتاجية يجب وضع مجلد `data/` على وحدة تخزين دائمة، أو نقل هذه السجلات لاحقاً إلى PostgreSQL أيضاً.

## 1. ماذا يفعل الكود الحالي عند تشغيله؟

يقرأ التطبيق المتغير `OMNI_VECTOR_DSN`، أو `DATABASE_URL` كبديل. إذا وجد رابطاً صالحاً، ينشئ `PostgresVectorBackend` ويستخدم جدول `omni_semantic_memory`. إن لم يجد رابطاً، يستخدم ذاكرة متجهية محلية غير دائمة. وعند وجود رابط خاطئ مع `ALLOW_LOCAL_VECTOR_FALLBACK=1`، يتراجع التطبيق إلى الوضع المحلي؛ لذلك يجب منع هذا التراجع في الإنتاج.

| الإعداد | القيمة الإنتاجية المقترحة | أثره |
| --- | --- | --- |
| `OMNI_VECTOR_DSN` | رابط PostgreSQL محفوظ كسر | يفعّل `PostgresVectorBackend` |
| `ALLOW_LOCAL_VECTOR_FALLBACK` | `0` | يفشل الإقلاع بدلاً من فقدان الاستمرارية بصمت |
| `OMNI_MAX_UPLOAD_MB` | `64` أو قيمة مدروسة | يحدد سقف CSV المرفوع |
| `OMNI_MAX_UPLOAD_ROWS` | `1000000` أو قيمة مدروسة | يحدد سقف الصفوف التي يحللها Data Analysis Lab |

> المخطط الحالي يستخدم متجهات حتمية محلية ذات 64 بُعداً لأغراض الاختبار. هذا يثبت التخزين والاسترجاع في pgvector، لكنه ليس بديلاً عن نموذج Embeddings إنتاجي. عند استبداله، يجب تثبيت أبعاد النموذج في كل من `PostgresVectorBackend(..., dimensions=D, embedding_fn=...)` وعمود `vector(D)`، ثم إعادة فهرسة السجلات القديمة.

## 2. تجهيز PostgreSQL حقيقي يدعم pgvector

استخدم خدمة PostgreSQL مُدارة تدعم `pgvector` أو خادماً ذاتياً فيه الامتداد مثبتاً. تحقق من أن مستخدم النشر يملك حق تنفيذ `CREATE EXTENSION`؛ الكود الحالي يستدعي `ensure_schema()` عند الإقلاع لإنشاء الامتداد والجدول والفهرس الأساسي عند غيابها.

اتصل بقاعدة البيانات عبر أداة SQL الخاصة بالمزود أو `psql` ثم نفذ:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS omni_semantic_memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS omni_semantic_memory_user_idx
    ON omni_semantic_memory (user_id);
```

يستخدم المحرك الحالي مسافة **cosine** عبر العامل `<=>`. عندما يصبح جدول الذاكرة كبيراً بما يكفي ليبرر البحث التقريبي، أضف فهرس HNSW المتوافق مع cosine بعد اختبار الاستدعاء وجودته:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS omni_semantic_memory_embedding_hnsw
    ON omni_semantic_memory
    USING hnsw (embedding vector_cosine_ops);
```

يوفر pgvector بحثاً دقيقاً افتراضياً، بينما يبدّل HNSW وIVFFlat جزءاً من الدقة مقابل الأداء؛ لذلك لا تضف فهرساً تقريبياً دون قياس الاستدعاء الفعلي في بياناتك [1]. إذا كان لكل مؤسسة عدد قليل من السجلات، فالبحث الدقيق مع فهرس `user_id` قد يكون أبسط وأكثر قابلية للتنبؤ.

## 3. حماية الأسرار والاتصال

احفظ رابط الاتصال في مدير أسرار مزودك السحابي أو في متغيرات خدمة النشر. لا تضعه في GitHub، ولا ترسله في ملف مرفوع. استخدم TLS؛ يقبل Psycopg رابطاً مثل:

```bash
export OMNI_VECTOR_DSN='postgresql://omni_runtime:REPLACE_ME@db.example.com:5432/omni?sslmode=require'
export ALLOW_LOCAL_VECTOR_FALLBACK=0
```

تشفير TLS مدعوم أصلاً في PostgreSQL عندما يفعّله الخادم، ويمكن للعميل استخدام اتصال مشفر إلى القاعدة [2]. في الخدمات المُدارة، اتبع ملف CA وطريقة التحقق التي يحددها المزود؛ استخدم `verify-full` عندما تزود التطبيق بشهادة الجذر الصحيحة واسم المضيف المطابق.

**فصل الصلاحيات الموصى به:** نفذ `CREATE EXTENSION` وإنشاء الجداول بواسطة حساب ترحيل محدود الاستخدام، ثم شغل التطبيق بحساب لا يملك إلا `CONNECT` و`USAGE` و`SELECT/INSERT/UPDATE` على جدول الذاكرة. لاحظ أن نسخة المشروع الحالية تنفذ التهيئة الآلية عند بدء التشغيل؛ لكي تستخدم حساب تشغيل محدوداً تماماً، أضف خطوة ترحيل صريحة وغيّر بدء التشغيل مستقبلاً ليتجاوز `ensure_schema()` بعد تحقق المخطط.

## 4. تشغيل Omni-Agent مع pgvector

نفذ الأوامر داخل جذر المستودع:

```bash
git clone https://github.com/majid-alsakani/omni-agent-ai.git
cd omni-agent-ai

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r backend/requirements-vector.txt

export OMNI_VECTOR_DSN='postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require'
export ALLOW_LOCAL_VECTOR_FALLBACK=0
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

في Docker، لا تحتفظ ملفات JSON داخل طبقة الحاوية؛ اربط وحدة دائمة للمجلد `data/`:

```bash
docker build -t omni-agent:3.3 .
docker run --rm -p 8000:8000 \
  --env OMNI_VECTOR_DSN="$OMNI_VECTOR_DSN" \
  --env ALLOW_LOCAL_VECTOR_FALLBACK=0 \
  --volume "$(pwd)/data:/app/data" \
  omni-agent:3.3
```

تحقق من أن الاتصال ليس محلياً:

```bash
curl http://127.0.0.1:8000/health
```

يجب أن تحتوي الاستجابة على:

```json
{
  "status": "ok",
  "vector_store": "postgres-pgvector"
}
```

ثم تحقق من القاعدة نفسها:

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
SELECT user_id, count(*) FROM omni_semantic_memory GROUP BY user_id;
```

## 5. تشغيل Command Center محلياً خطوة بخطوة

### أ. وضع التطوير السريع من دون قاعدة خارجية

إذا كان هدفك تجربة الواجهة فقط، نفذ ما يلي. سيظهر في البطاقة العلوية أن `Vector Store` هو `local-hashed-vector`:

```bash
cd omni-agent-ai
source .venv/bin/activate
unset OMNI_VECTOR_DSN DATABASE_URL
uvicorn backend.main:app --reload --port 8000
```

افتح المتصفح على `http://127.0.0.1:8000`. ستظهر لوحة مركز المهام ثم أربع بطاقات: حالة المحرك، عدد سجلات الذاكرة، نوع Vector Store، وعدد الأدوات المسموحة.

### ب. تشغيل مهمة وكلاء متعددة

في قسم **مركز المهام**:

1. اكتب هوية ثابتة مثل `demo-sales-01` في حقل **هوية المستخدم**.
2. اختر `Multi-Agent` أو اترك `Auto` لمهام التخطيط المعقدة.
3. اكتب مهمة مثل: `حلل فرصة توسع في سوق جديد، حدد مؤشرات النجاح، وافحص المخاطر قبل التوصية.`
4. اضغط **تشغيل المهمة**.

سيظهر مخطط التنسيق والنتيجة الموحدة، ثم ستُحدَّث بطاقة الذاكرة. هذه العملية لا تنفذ إجراءً خارجياً.

### ج. استعراض تقرير مبيعات من الواجهة

في قسم **Data Analysis Lab**:

1. اضغط **اختر ملف CSV**.
2. للتجربة السريعة، اختر `tests/fixtures/uci_online_retail_excerpt.csv`.
3. اضغط **حلل البيانات**.
4. اقرأ بطاقة النتيجة: عدد الصفوف والأعمدة، درجة الجودة، القيم الناقصة، العلاقة الرقمية الأقوى، وتوصيات الوكلاء.
5. ستظهر مساهمات `Data Profiling` و`Insight` و`Data Quality` و`Sales Intelligence`، بما فيها الإيراد والطلبات والإلغاءات والأسواق عند اكتشاف الأعمدة التجارية.

الحدود الافتراضية الحالية هي **64MB** و**1,000,000 صف** و**100 عمود**. لا يحتفظ Data Analysis Lab بمحتوى CSV؛ يسجل ملخصاً تجميعياً فقط في ذاكرة الجلسة.

### د. إعادة إنتاج تقرير المبيعات الكبير

نزل ملف **Online Retail.xlsx** من UCI، ثم حوّله إلى CSV:

```bash
python scripts/prepare_online_retail_dataset.py \
  /path/to/Online\ Retail.xlsx \
  /tmp/online_retail.csv
```

بعدها اختر `/tmp/online_retail.csv` في الواجهة. ملف الاختبار الذي تحقق منه المشروع يحتوي على 541,909 معاملة و8 حقول؛ حجمه 45.81MB، لذا يقع ضمن السقف الافتراضي [3].

### هـ. الاستعراض عبر API عند الحاجة

يعطي هذا الأمر التقرير نفسه بشكل JSON يمكن حفظه أو ربطه بأداة خارجية:

```bash
curl -sS -X POST http://127.0.0.1:8000/analyze-data \
  -F 'file=@tests/fixtures/uci_online_retail_excerpt.csv;type=text/csv' \
  -F 'user_id=demo-sales-01' \
  -F 'session_id=sales-demo' \
  | python3 -m json.tool
```

ولإنشاء مسودة قرار للتوأم الاستراتيجي من الملف نفسه:

```bash
curl -sS -X POST http://127.0.0.1:8000/strategic-twin/analyze-data \
  -F 'file=@tests/fixtures/uci_online_retail_excerpt.csv;type=text/csv' \
  -F 'objective=تقييم تجربة توسع محدودة مع مراقبة الإلغاءات وقيمة الطلبات' \
  -F 'user_id=demo-sales-01' \
  -F 'session_id=sales-demo' \
  | python3 -m json.tool
```

لا يصبح القرار في الذاكرة الدلالية حتى تستدعي `POST /strategic-twin/approve` بمعرف المسودة وملاحظة اعتماد بشرية. بعد الاعتماد، يمكن التحقق من الاستمرارية عبر `GET /strategic-twin/precedents?objective=...&user_id=demo-sales-01` ثم رؤية سجل جديد في `omni_semantic_memory` عند استخدام pgvector.

## 6. قائمة تحقق وتشخيص سريع

| العرض | السبب المحتمل | الإجراء |
| --- | --- | --- |
| `vector_store` يساوي `local-hashed-vector` | لم يقرأ التطبيق رابطاً أو لم يتم تعريفه | افحص `OMNI_VECTOR_DSN` وأعد تشغيل العملية |
| `local-hashed-vector-fallback` | فشل اتصال pgvector لكن التراجع مسموح | افحص سجلات التطبيق، واضبط `ALLOW_LOCAL_VECTOR_FALLBACK=0` في الإنتاج |
| فشل `CREATE EXTENSION vector` | المزود لا يدعم pgvector أو الدور بلا صلاحية | فعّل الامتداد من لوحة المزود أو استخدم دور ترحيل مخول |
| خطأ أبعاد `vector` | تغير نموذج Embeddings أو أبعاده | وحّد قيمة الأبعاد في الكود والجدول، ثم أعد توليد المتجهات |
| اختفاء الذاكرة العرضية بعد إعادة النشر | مجلد `data/` داخل حاوية مؤقتة | اربط volume دائماً أو انقل الذاكرة العرضية والمسودات إلى PostgreSQL |
| رفض ملف المبيعات | تجاوز السقف أو لم يكن CSV صالحاً | راجع `OMNI_MAX_UPLOAD_MB` و`OMNI_MAX_UPLOAD_ROWS` وترميز الملف |

## References

[1]: https://github.com/pgvector/pgvector "pgvector — البحث المتجهي والفهارس والتشابه في PostgreSQL"
[2]: https://www.postgresql.org/docs/current/ssl-tcp.html "PostgreSQL Documentation — Secure TCP/IP Connections with SSL"
[3]: https://archive.ics.uci.edu/dataset/352/online+retail "UCI Machine Learning Repository — Online Retail"
