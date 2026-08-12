# مصادر التحقق السحابي

## pgvector الرسمي
الرابط: https://github.com/pgvector/pgvector

أكد المصدر أن pgvector يضيف البحث بالتشابه إلى PostgreSQL، وأن العمود يُعرّف بصيغة `vector(n)`. يوضح أيضاً إدخال المتجهات والبحث باستخدام عامل المسافة `<->`، ويدعم فهارس البحث التقريبي مثل HNSW وIVFFlat.

## Supabase الرسمي
الرابط: https://supabase.com/docs/guides/database/extensions/pgvector

يوضح الدليل أن اسم امتداد PostgreSQL هو `vector`، وأنه يمكن تفعيله من قسم Extensions، ثم إنشاء عمود مثل `extensions.vector(384)` وتخزين embeddings الناتجة من نموذج تحويل. ينبه الدليل إلى أن التصفية مع IVFFlat/HNSW قد تعيد عدداً أقل من النتائج المطلوبة دون iterative search، لذلك يجب اختبار الفهارس مع مرشح user_id/tenant_id.

## ملاحظة تصميمية لـ Omni-Agent
يستخدم المشروع حالياً 64 بُعداً للـ fallback المحلي والـ adapter التجريبي. عند اختيار نموذج embeddings إنتاجي يجب مطابقة أبعاد العمود مع النموذج، استخدام نفس النموذج في الإدخال والاسترجاع، وإعادة فهرسة البيانات عند تغيير النموذج. يجب إبقاء `user_id` ويفضل `tenant_id` ضمن شروط البحث والعزل.
