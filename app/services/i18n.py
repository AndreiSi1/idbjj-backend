"""Локализация бота (RU / EN / ES / PT-BR / DE).

Все строки UI собраны здесь по ключам. dialog.py берёт текст через t(lang, key).
Канонические ключи полей анкет (Пояс, Стаж...) НЕ переводятся — они совпадают с
плейсхолдерами системных промптов; переводится только отображаемый вопрос.

AI отвечает на языке пользователя: ai.build_system_prompt добавляет директиву из
AI_LANG. База знаний остаётся на русском — LLM читает её и отвечает на нужном языке.
"""
from __future__ import annotations

# Язык по умолчанию / порядок выбора
DEFAULT_LANG = "ru"
LANGS = ("ru", "en", "es", "pt", "de")

# Кнопки выбора языка (показываются до согласия).
LANG_BUTTONS = [
    [("🇷🇺 Русский", "lang:ru"), ("🇬🇧 English", "lang:en")],
    [("🇪🇸 Español", "lang:es"), ("🇧🇷 Português", "lang:pt")],
    [("🇩🇪 Deutsch", "lang:de")],
]

# Экран выбора языка — нейтрально-многоязычный (язык ещё не выбран).
LANG_PROMPT = "🥋 Выбери язык / Choose your language / Elige idioma / Escolha o idioma / Sprache wählen:"

# Директива языка ответа — ставится В НАЧАЛО системного промпта (иначе модель
# матчится с русским контекстом базы знаний). Формулировка усиленная.
AI_LANG = {
    "ru": "Отвечай на русском языке.",
    "en": "CRITICAL RULE: Write your ENTIRE response in English only. The instructions and reference materials below are in Russian, but you MUST answer in English.",
    "es": "REGLA CRÍTICA: Escribe TODA tu respuesta únicamente en español. Las instrucciones y los materiales de referencia a continuación están en ruso, pero DEBES responder en español.",
    "pt": "REGRA CRÍTICA: Escreva TODA a sua resposta apenas em português (Brasil). As instruções e os materiais de referência abaixo estão em russo, mas você DEVE responder em português.",
    "de": "WICHTIGE REGEL: Schreibe deine GESAMTE Antwort ausschließlich auf Deutsch. Die Anweisungen und Referenzmaterialien unten sind auf Russisch, aber du MUSST auf Deutsch antworten.",
}

# Пояса: ключ → подпись по языкам (эмодзи общий).
BELT_LABELS = {
    "white":  {"ru": "Белый пояс",       "en": "White belt",  "es": "Cinturón blanco",  "pt": "Faixa branca",  "de": "Weißer Gürtel"},
    "blue":   {"ru": "Синий пояс",        "en": "Blue belt",   "es": "Cinturón azul",    "pt": "Faixa azul",    "de": "Blauer Gürtel"},
    "purple": {"ru": "Фиолетовый пояс",   "en": "Purple belt", "es": "Cinturón violeta", "pt": "Faixa roxa",    "de": "Lila Gürtel"},
    "brown":  {"ru": "Коричневый пояс",   "en": "Brown belt",  "es": "Cinturón marrón",  "pt": "Faixa marrom",  "de": "Brauner Gürtel"},
    "black":  {"ru": "Чёрный пояс",       "en": "Black belt",  "es": "Cinturón negro",   "pt": "Faixa preta",   "de": "Schwarzer Gürtel"},
}

# Уровневые тиры (по номеру уровня) на 4 языках.
LEVEL_TITLES = {
    "ru": [(1, "Новичок мата"), (3, "Боец"), (5, "Атлет"), (8, "Ветеран мата"), (12, "Мастер")],
    "en": [(1, "Mat Newcomer"), (3, "Fighter"), (5, "Athlete"), (8, "Mat Veteran"), (12, "Master")],
    "es": [(1, "Novato del tatami"), (3, "Luchador"), (5, "Atleta"), (8, "Veterano del tatami"), (12, "Maestro")],
    "pt": [(1, "Novato do tatame"), (3, "Lutador"), (5, "Atleta"), (8, "Veterano do tatame"), (12, "Mestre")],
    "de": [(1, "Matten-Neuling"), (3, "Kämpfer"), (5, "Athlet"), (8, "Matten-Veteran"), (12, "Meister")],
}

T: dict[str, dict[str, str]] = {
    "ru": {
        "consent": (
            "👋 Добро пожаловать в клуб ID BJJ!\n\n"
            "Чтобы продолжить, прими условия использования и согласие на обработку "
            "персональных данных:\n• Соглашение: {terms}\n• Обработка данных: {privacy}\n\n"
            "Нажимая «Принимаю», ты соглашаешься с этими документами."
        ),
        "btn_accept": "✅ Принимаю",
        "menu_text": "🥋 Клуб ID BJJ — бразильское джиу-джитсу.\n\nВыбери раздел 👇",
        "btn_trainer": "🥋 Онлайн-тренер",
        "btn_enc": "📚 Энциклопедия BJJ",
        "btn_diet": "🥗 Диета",
        "btn_progress": "📈 Мой прогресс",
        "btn_oss": "🌐 Oss — соцсеть (скоро)",
        "btn_contact": "✉️ Связаться с тренером",
        "btn_lang": "🌐 Сменить язык",
        "lang_changed": "✅ Язык переключён на русский.",
        "btn_menu": "⬅️ Главное меню",
        "btn_cancel": "✖️ Отмена",
        "tr_intro": "Пройди короткую анкету — тренер будет учитывать твой профиль.",
        "tr_q_belt": "🥋 Какой у тебя пояс и сколько полосок? (например: синий, 2 полоски)",
        "tr_q_exp": "📅 Сколько месяцев занимаешься BJJ?",
        "tr_q_freq": "🔁 Сколько тренировок в неделю?",
        "tr_q_goal": "🎯 Какая у тебя цель? (например: подтянуть гард, подготовка к турниру, ЗОЖ)",
        "tr_q_injury": "🩹 Есть ограничения или травмы? (если нет — напиши «нет»)",
        "dt_intro": "Заполни анкету — посчитаю калории и БЖУ по формуле Миффлина-Сан Жеора.",
        "dt_q_sex": "⚧ Твой пол? (мужской / женский)",
        "dt_q_age": "🎂 Сколько тебе полных лет?",
        "dt_q_height": "📏 Рост в см?",
        "dt_q_weight": "⚖️ Вес в кг?",
        "dt_q_activity": "🏃 Активность: малоподвижный / лёгкая / средняя / высокая / очень высокая?",
        "dt_q_goal": "🎯 Цель: похудеть / набрать мышцы / поддержать форму / ЗОЖ / сгонка веса?",
        "anketa_saved": "✅ Анкета сохранена!",
        "greet_trainer": "🥋 Я твой онлайн-тренер. Спрашивай про технику, план тренировок, прогресс.",
        "btn_comp": "🏆 План к соревнованиям",
        "comp_intro": "🏆 Соберу персональный план подготовки к турниру. Ответь на 3 вопроса.",
        "comp_q_weeks": "📅 Сколько недель осталось до соревнований? (числом, например 8)",
        "comp_q_format": "🥋 Формат турнира?",
        "cf_gi": "🥋 Gi (в кимоно)",
        "cf_nogi": "🩳 No-Gi (без кимоно)",
        "cf_both": "🔁 Gi + No-Gi",
        "comp_q_goal": "🎯 Цель на турнир? (например: выиграть, набраться опыта, отработать коронку)",
        "comp_generating": "⏳ Составляю твой план подготовки…",
        "comp_user_req": "Составь мой план подготовки к соревнованиям по моему профилю и параметрам турнира.",
        "btn_journal": "📓 Дневник тренировок",
        "jr_title": "📓 Дневник тренировок",
        "jr_empty": "Дневник пуст. Запиши первую тренировку — я буду помнить, что ты проходил, и помогу собрать это в систему.",
        "jr_recent": "Последние записи:",
        "jr_count": "Всего тренировок в дневнике: {n}.",
        "btn_jr_add": "✍️ Записать тренировку",
        "btn_jr_review": "📊 Разбор от тренера",
        "jr_ask": "Что отрабатывали на тренировке? Напиши коротко: приёмы/позиции, что получалось, над чем работать.",
        "jr_saved": "✅ Записано! В дневнике уже {n}. Возвращайся после каждой тренировки 💪",
        "jr_review_wait": "⏳ Анализирую твой дневник…",
        "jr_need_entries": "Сначала запиши хотя бы одну тренировку — потом разберу.",
        "jr_user_req": "Разбери мой дневник тренировок по моему профилю.",
        "btn_jr_plan": "🗺️ Мой геймплан",
        "jr_plan_wait": "🗺️ Собираю твой геймплан из дневника…",
        "jr_plan_req": "Собери мой геймплан (карту игры) из дневника по моему профилю.",
        "greet_encyclopedia": "📚 Я энциклопедия BJJ. Спроси про историю, пояса, гарды, приёмы, чемпионов.",
        "greet_dietolog": "🥗 Я диетолог клуба. Спрашивай про питание, калории, меню под тренировки.",
        "ai_unavailable": "⚠️ AI сейчас недоступен, попробуй позже.",
        "diet_calc": "Посчитай мои калории и БЖУ по анкете.",
        "contact_ask": "✉️ С чем хочешь обратиться?",
        "ck_trial": "🆓 Пробное занятие",
        "ck_question": "❓ Вопрос тренеру",
        "ck_sub": "💳 Абонемент / цены",
        "contact_phone": "Тип заявки: {kind}.\n📞 Оставь телефон (+7…) — тренер свяжется с тобой.",
        "contact_done": "✅ Заявка принята! Тренер свяжется с тобой в ближайшее время.",
        "oss_text": (
            "🌐 Oss — социальная сеть для джитсеров\n\n"
            "Как Instagram, только для своих: лента тренировок, друзья и партнёры, "
            "залы по всему миру, обмен опытом и достижениями.\n\n"
            "🚧 Раздел в разработке — скоро откроем! Следи за анонсами здесь, в боте."
        ),
        "pg_title": "📈 Твой прогресс",
        "pg_rank": "Ранг",
        "pg_rank_none": "Ранг: не указан (пройди анкету «Онлайн-тренер»)",
        "pg_level": "Уровень",
        "pg_to_next": "До следующего уровня",
        "pg_hint": "XP начисляется за анкеты, вопросы ассистентам и заявки. Возвращайся чаще! 💪",
        "btn_share_progress": "📤 Поделиться карточкой",
        "card_level": "Уровень",
        "share_caption": "🥋 Мой прогресс в BJJ: {belt}, {title} (уровень {level}). Качаю джиу-джитсу с ID BJJ 👉 {url}",
        "btn_invite": "🤝 Пригласить друга",
        "invite_text": "🤝 Приглашай друзей в ID BJJ!\n\nКинь другу свою ссылку — когда он зайдёт, вы ОБА получите бонус XP к уровню.\n\nТвоя ссылка:\n{link}\n\nПриглашено друзей: {count}",
        "ref_reward": "🎉 По твоей ссылке в ID BJJ пришёл друг! +{xp} XP. Спасибо, что растишь сообщество 🤝",
    },
    "en": {
        "consent": (
            "👋 Welcome to ID BJJ!\n\n"
            "To continue, please accept the Terms of Use and consent to personal data "
            "processing:\n• Terms: {terms}\n• Privacy: {privacy}\n\n"
            "By tapping “Accept”, you agree to these documents."
        ),
        "btn_accept": "✅ Accept",
        "menu_text": "🥋 ID BJJ — Brazilian Jiu-Jitsu.\n\nChoose a section 👇",
        "btn_trainer": "🥋 Online coach",
        "btn_enc": "📚 BJJ Encyclopedia",
        "btn_diet": "🥗 Nutrition",
        "btn_progress": "📈 My progress",
        "btn_oss": "🌐 Oss — social (soon)",
        "btn_contact": "✉️ Contact a coach",
        "btn_lang": "🌐 Change language",
        "lang_changed": "✅ Language switched to English.",
        "btn_menu": "⬅️ Main menu",
        "btn_cancel": "✖️ Cancel",
        "tr_intro": "Fill in a short form — the coach will tailor advice to your profile.",
        "tr_q_belt": "🥋 What's your belt and how many stripes? (e.g. blue, 2 stripes)",
        "tr_q_exp": "📅 How many months have you trained BJJ?",
        "tr_q_freq": "🔁 How many sessions per week?",
        "tr_q_goal": "🎯 What's your goal? (e.g. improve guard, prep for a tournament, fitness)",
        "tr_q_injury": "🩹 Any limitations or injuries? (if none, type “no”)",
        "dt_intro": "Fill in the form — I'll calculate calories and macros (Mifflin-St Jeor).",
        "dt_q_sex": "⚧ Your sex? (male / female)",
        "dt_q_age": "🎂 Your age (full years)?",
        "dt_q_height": "📏 Height in cm?",
        "dt_q_weight": "⚖️ Weight in kg?",
        "dt_q_activity": "🏃 Activity: sedentary / light / moderate / high / very high?",
        "dt_q_goal": "🎯 Goal: lose fat / build muscle / maintain / health / weight cut?",
        "anketa_saved": "✅ Profile saved!",
        "greet_trainer": "🥋 I'm your online coach. Ask about technique, training plans, progress.",
        "btn_comp": "🏆 Competition plan",
        "comp_intro": "🏆 I'll build a personal tournament prep plan. Answer 3 questions.",
        "comp_q_weeks": "📅 How many weeks until the competition? (a number, e.g. 8)",
        "comp_q_format": "🥋 Tournament format?",
        "cf_gi": "🥋 Gi",
        "cf_nogi": "🩳 No-Gi",
        "cf_both": "🔁 Gi + No-Gi",
        "comp_q_goal": "🎯 Goal for the tournament? (e.g. win, gain experience, drill a signature move)",
        "comp_generating": "⏳ Building your prep plan…",
        "comp_user_req": "Build my competition prep plan from my profile and tournament parameters.",
        "btn_journal": "📓 Training journal",
        "jr_title": "📓 Training journal",
        "jr_empty": "Your journal is empty. Log your first session — I'll remember what you drilled and help turn it into a system.",
        "jr_recent": "Recent entries:",
        "jr_count": "Sessions logged: {n}.",
        "btn_jr_add": "✍️ Log a session",
        "btn_jr_review": "📊 Coach's review",
        "jr_ask": "What did you drill today? Keep it short: techniques/positions, what worked, what to improve.",
        "jr_saved": "✅ Logged! {n} sessions in your journal. Come back after every training 💪",
        "jr_review_wait": "⏳ Analyzing your journal…",
        "jr_need_entries": "Log at least one session first — then I'll review it.",
        "jr_user_req": "Review my training journal based on my profile.",
        "btn_jr_plan": "🗺️ My game plan",
        "jr_plan_wait": "🗺️ Building your game plan from the journal…",
        "jr_plan_req": "Build my game plan (game map) from my journal based on my profile.",
        "greet_encyclopedia": "📚 I'm the BJJ encyclopedia. Ask about history, belts, guards, techniques, champions.",
        "greet_dietolog": "🥗 I'm the club nutritionist. Ask about food, calories, meal plans for training.",
        "ai_unavailable": "⚠️ AI is unavailable right now, try again later.",
        "diet_calc": "Calculate my calories and macros from my profile.",
        "contact_ask": "✉️ What would you like to ask about?",
        "ck_trial": "🆓 Free trial class",
        "ck_question": "❓ Question to a coach",
        "ck_sub": "💳 Membership / prices",
        "contact_phone": "Request type: {kind}.\n📞 Leave your phone — a coach will contact you.",
        "contact_done": "✅ Request received! A coach will get in touch shortly.",
        "oss_text": (
            "🌐 Oss — the social network for grapplers\n\n"
            "Like Instagram, but for your tribe: a training feed, friends and partners, "
            "gyms worldwide, sharing experience and achievements.\n\n"
            "🚧 In development — launching soon! Watch for announcements here in the bot."
        ),
        "pg_title": "📈 Your progress",
        "pg_rank": "Rank",
        "pg_rank_none": "Rank: not set (complete the “Online coach” form)",
        "pg_level": "Level",
        "pg_to_next": "To next level",
        "pg_hint": "XP is earned for forms, AI questions and requests. Come back often! 💪",
        "btn_share_progress": "📤 Share my card",
        "card_level": "Level",
        "share_caption": "🥋 My BJJ progress: {belt}, {title} (level {level}). Leveling up my jiu-jitsu with ID BJJ 👉 {url}",
        "btn_invite": "🤝 Invite a friend",
        "invite_text": "🤝 Invite friends to ID BJJ!\n\nSend a friend your link — when they join, you BOTH get bonus XP.\n\nYour link:\n{link}\n\nFriends invited: {count}",
        "ref_reward": "🎉 A friend joined ID BJJ via your link! +{xp} XP. Thanks for growing the community 🤝",
    },
    "es": {
        "consent": (
            "👋 ¡Bienvenido a ID BJJ!\n\n"
            "Para continuar, acepta los Términos de uso y el consentimiento de "
            "tratamiento de datos:\n• Términos: {terms}\n• Privacidad: {privacy}\n\n"
            "Al pulsar «Aceptar», aceptas estos documentos."
        ),
        "btn_accept": "✅ Aceptar",
        "menu_text": "🥋 ID BJJ — Jiu-Jitsu Brasileño.\n\nElige una sección 👇",
        "btn_trainer": "🥋 Entrenador online",
        "btn_enc": "📚 Enciclopedia BJJ",
        "btn_diet": "🥗 Nutrición",
        "btn_progress": "📈 Mi progreso",
        "btn_oss": "🌐 Oss — red social (pronto)",
        "btn_contact": "✉️ Contactar a un coach",
        "btn_lang": "🌐 Cambiar idioma",
        "lang_changed": "✅ Idioma cambiado a español.",
        "btn_menu": "⬅️ Menú principal",
        "btn_cancel": "✖️ Cancelar",
        "tr_intro": "Completa un breve formulario — el coach adaptará los consejos a tu perfil.",
        "tr_q_belt": "🥋 ¿Cuál es tu cinturón y cuántos grados? (p. ej.: azul, 2 grados)",
        "tr_q_exp": "📅 ¿Cuántos meses entrenas BJJ?",
        "tr_q_freq": "🔁 ¿Cuántas sesiones por semana?",
        "tr_q_goal": "🎯 ¿Cuál es tu objetivo? (p. ej. mejorar la guardia, preparar un torneo, salud)",
        "tr_q_injury": "🩹 ¿Alguna limitación o lesión? (si no, escribe «no»)",
        "dt_intro": "Completa el formulario — calcularé calorías y macros (Mifflin-St Jeor).",
        "dt_q_sex": "⚧ ¿Tu sexo? (masculino / femenino)",
        "dt_q_age": "🎂 ¿Tu edad (años cumplidos)?",
        "dt_q_height": "📏 ¿Altura en cm?",
        "dt_q_weight": "⚖️ ¿Peso en kg?",
        "dt_q_activity": "🏃 Actividad: sedentario / ligera / moderada / alta / muy alta?",
        "dt_q_goal": "🎯 Objetivo: perder grasa / ganar músculo / mantener / salud / corte de peso?",
        "anketa_saved": "✅ ¡Perfil guardado!",
        "greet_trainer": "🥋 Soy tu entrenador online. Pregunta sobre técnica, planes y progreso.",
        "btn_comp": "🏆 Plan para competir",
        "comp_intro": "🏆 Prepararé un plan personal para tu torneo. Responde 3 preguntas.",
        "comp_q_weeks": "📅 ¿Cuántas semanas faltan para la competición? (un número, p. ej. 8)",
        "comp_q_format": "🥋 ¿Formato del torneo?",
        "cf_gi": "🥋 Gi (con kimono)",
        "cf_nogi": "🩳 No-Gi (sin kimono)",
        "cf_both": "🔁 Gi + No-Gi",
        "comp_q_goal": "🎯 ¿Objetivo del torneo? (p. ej. ganar, ganar experiencia, pulir tu técnica estrella)",
        "comp_generating": "⏳ Preparando tu plan…",
        "comp_user_req": "Prepara mi plan de preparación para la competición según mi perfil y los datos del torneo.",
        "btn_journal": "📓 Diario de entrenos",
        "jr_title": "📓 Diario de entrenos",
        "jr_empty": "Tu diario está vacío. Registra tu primer entreno — recordaré lo que practicaste y te ayudaré a darle sistema.",
        "jr_recent": "Últimas entradas:",
        "jr_count": "Entrenos registrados: {n}.",
        "btn_jr_add": "✍️ Registrar entreno",
        "btn_jr_review": "📊 Análisis del coach",
        "jr_ask": "¿Qué practicaste hoy? Breve: técnicas/posiciones, qué salió bien, qué mejorar.",
        "jr_saved": "✅ ¡Registrado! {n} entrenos en tu diario. Vuelve después de cada entreno 💪",
        "jr_review_wait": "⏳ Analizando tu diario…",
        "jr_need_entries": "Registra al menos un entreno primero — luego lo analizo.",
        "jr_user_req": "Analiza mi diario de entrenos según mi perfil.",
        "btn_jr_plan": "🗺️ Mi plan de juego",
        "jr_plan_wait": "🗺️ Armando tu plan de juego desde el diario…",
        "jr_plan_req": "Arma mi plan de juego (mapa de juego) desde mi diario según mi perfil.",
        "greet_encyclopedia": "📚 Soy la enciclopedia de BJJ. Pregunta sobre historia, cinturones, guardias, técnicas, campeones.",
        "greet_dietolog": "🥗 Soy el nutricionista del club. Pregunta sobre comida, calorías y menús para entrenar.",
        "ai_unavailable": "⚠️ La IA no está disponible ahora, inténtalo más tarde.",
        "diet_calc": "Calcula mis calorías y macros según mi perfil.",
        "contact_ask": "✉️ ¿Sobre qué quieres consultar?",
        "ck_trial": "🆓 Clase de prueba",
        "ck_question": "❓ Pregunta a un coach",
        "ck_sub": "💳 Membresía / precios",
        "contact_phone": "Tipo de solicitud: {kind}.\n📞 Deja tu teléfono — un coach te contactará.",
        "contact_done": "✅ ¡Solicitud recibida! Un coach te contactará pronto.",
        "oss_text": (
            "🌐 Oss — la red social para grapplers\n\n"
            "Como Instagram, pero para los tuyos: feed de entrenamientos, amigos y "
            "compañeros, gimnasios de todo el mundo, compartir experiencia y logros.\n\n"
            "🚧 En desarrollo — ¡pronto! Atento a los anuncios aquí en el bot."
        ),
        "pg_title": "📈 Tu progreso",
        "pg_rank": "Rango",
        "pg_rank_none": "Rango: sin definir (completa el formulario «Entrenador online»)",
        "pg_level": "Nivel",
        "pg_to_next": "Para el siguiente nivel",
        "pg_hint": "Ganas XP por formularios, preguntas a la IA y solicitudes. ¡Vuelve seguido! 💪",
        "btn_share_progress": "📤 Compartir tarjeta",
        "card_level": "Nivel",
        "share_caption": "🥋 Mi progreso en BJJ: {belt}, {title} (nivel {level}). Mejorando mi jiu-jitsu con ID BJJ 👉 {url}",
        "btn_invite": "🤝 Invitar a un amigo",
        "invite_text": "🤝 ¡Invita a tus amigos a ID BJJ!\n\nEnvía tu enlace a un amigo — cuando entre, AMBOS reciben XP de bonus.\n\nTu enlace:\n{link}\n\nAmigos invitados: {count}",
        "ref_reward": "🎉 ¡Un amigo entró a ID BJJ con tu enlace! +{xp} XP. Gracias por hacer crecer la comunidad 🤝",
    },
    "pt": {
        "consent": (
            "👋 Bem-vindo ao ID BJJ!\n\n"
            "Para continuar, aceite os Termos de uso e o consentimento de tratamento "
            "de dados:\n• Termos: {terms}\n• Privacidade: {privacy}\n\n"
            "Ao tocar em «Aceitar», você concorda com estes documentos."
        ),
        "btn_accept": "✅ Aceitar",
        "menu_text": "🥋 ID BJJ — Jiu-Jitsu Brasileiro.\n\nEscolha uma seção 👇",
        "btn_trainer": "🥋 Treinador online",
        "btn_enc": "📚 Enciclopédia de BJJ",
        "btn_diet": "🥗 Nutrição",
        "btn_progress": "📈 Meu progresso",
        "btn_oss": "🌐 Oss — rede social (em breve)",
        "btn_contact": "✉️ Falar com um treinador",
        "btn_lang": "🌐 Mudar idioma",
        "lang_changed": "✅ Idioma alterado para português.",
        "btn_menu": "⬅️ Menu principal",
        "btn_cancel": "✖️ Cancelar",
        "tr_intro": "Preencha um formulário rápido — o treinador vai considerar seu perfil.",
        "tr_q_belt": "🥋 Qual é a sua faixa e quantos graus? (ex.: azul, 2 graus)",
        "tr_q_exp": "📅 Há quantos meses você treina BJJ?",
        "tr_q_freq": "🔁 Quantos treinos por semana?",
        "tr_q_goal": "🎯 Qual é o seu objetivo? (ex.: melhorar a guarda, preparar um campeonato, saúde)",
        "tr_q_injury": "🩹 Alguma limitação ou lesão? (se não, escreva «não»)",
        "dt_intro": "Preencha o formulário — vou calcular calorias e macros (Mifflin-St Jeor).",
        "dt_q_sex": "⚧ Seu sexo? (masculino / feminino)",
        "dt_q_age": "🎂 Sua idade (anos completos)?",
        "dt_q_height": "📏 Altura em cm?",
        "dt_q_weight": "⚖️ Peso em kg?",
        "dt_q_activity": "🏃 Atividade: sedentário / leve / moderada / alta / muito alta?",
        "dt_q_goal": "🎯 Objetivo: perder gordura / ganhar músculo / manter / saúde / corte de peso?",
        "anketa_saved": "✅ Perfil salvo!",
        "greet_trainer": "🥋 Sou seu treinador online. Pergunte sobre técnica, planos de treino e progresso.",
        "btn_comp": "🏆 Plano para competição",
        "comp_intro": "🏆 Vou montar um plano pessoal para o seu campeonato. Responda 3 perguntas.",
        "comp_q_weeks": "📅 Quantas semanas faltam para a competição? (um número, ex.: 8)",
        "comp_q_format": "🥋 Formato do campeonato?",
        "cf_gi": "🥋 Gi (com kimono)",
        "cf_nogi": "🩳 No-Gi (sem kimono)",
        "cf_both": "🔁 Gi + No-Gi",
        "comp_q_goal": "🎯 Objetivo no campeonato? (ex.: vencer, ganhar experiência, treinar seu golpe principal)",
        "comp_generating": "⏳ Montando o seu plano…",
        "comp_user_req": "Monte o meu plano de preparação para a competição com base no meu perfil e nos dados do campeonato.",
        "btn_journal": "📓 Diário de treinos",
        "jr_title": "📓 Diário de treinos",
        "jr_empty": "Seu diário está vazio. Registre seu primeiro treino — vou lembrar o que você treinou e ajudar a transformar em sistema.",
        "jr_recent": "Últimas entradas:",
        "jr_count": "Treinos registrados: {n}.",
        "btn_jr_add": "✍️ Registrar treino",
        "btn_jr_review": "📊 Análise do treinador",
        "jr_ask": "O que você treinou hoje? Curto: técnicas/posições, o que funcionou, o que melhorar.",
        "jr_saved": "✅ Registrado! {n} treinos no seu diário. Volte depois de cada treino 💪",
        "jr_review_wait": "⏳ Analisando seu diário…",
        "jr_need_entries": "Registre pelo menos um treino primeiro — depois eu analiso.",
        "jr_user_req": "Analise meu diário de treinos com base no meu perfil.",
        "btn_jr_plan": "🗺️ Meu game plan",
        "jr_plan_wait": "🗺️ Montando seu game plan a partir do diário…",
        "jr_plan_req": "Monte meu game plan (mapa de jogo) a partir do meu diário com base no meu perfil.",
        "greet_encyclopedia": "📚 Sou a enciclopédia de BJJ. Pergunte sobre história, faixas, guardas, técnicas, campeões.",
        "greet_dietolog": "🥗 Sou o nutricionista do clube. Pergunte sobre alimentação, calorias e cardápios para treino.",
        "ai_unavailable": "⚠️ A IA está indisponível agora, tente mais tarde.",
        "diet_calc": "Calcule minhas calorias e macros pelo meu perfil.",
        "contact_ask": "✉️ Sobre o que você quer falar?",
        "ck_trial": "🆓 Aula experimental",
        "ck_question": "❓ Pergunta ao treinador",
        "ck_sub": "💳 Mensalidade / preços",
        "contact_phone": "Tipo de solicitação: {kind}.\n📞 Deixe seu telefone — um treinador entrará em contato.",
        "contact_done": "✅ Solicitação recebida! Um treinador falará com você em breve.",
        "oss_text": (
            "🌐 Oss — a rede social dos grapplers\n\n"
            "Como o Instagram, mas para os seus: feed de treinos, amigos e parceiros, "
            "academias pelo mundo, troca de experiência e conquistas.\n\n"
            "🚧 Em desenvolvimento — em breve! Fique de olho nos anúncios aqui no bot."
        ),
        "pg_title": "📈 Seu progresso",
        "pg_rank": "Graduação",
        "pg_rank_none": "Graduação: não definida (preencha o formulário «Treinador online»)",
        "pg_level": "Nível",
        "pg_to_next": "Para o próximo nível",
        "pg_hint": "Você ganha XP por formulários, perguntas à IA e solicitações. Volte sempre! 💪",
        "btn_share_progress": "📤 Compartilhar card",
        "card_level": "Nível",
        "share_caption": "🥋 Meu progresso no BJJ: {belt}, {title} (nível {level}). Evoluindo meu jiu-jitsu com ID BJJ 👉 {url}",
        "btn_invite": "🤝 Convidar um amigo",
        "invite_text": "🤝 Convide amigos para o ID BJJ!\n\nMande seu link para um amigo — quando ele entrar, VOCÊS DOIS ganham XP de bônus.\n\nSeu link:\n{link}\n\nAmigos convidados: {count}",
        "ref_reward": "🎉 Um amigo entrou no ID BJJ pelo seu link! +{xp} XP. Obrigado por crescer a comunidade 🤝",
    },
    "de": {
        "consent": (
            "👋 Willkommen im ID BJJ Club!\n\n"
            "Um fortzufahren, akzeptiere bitte die Nutzungsbedingungen und die Einwilligung "
            "zur Verarbeitung personenbezogener Daten:\n• Bedingungen: {terms}\n• Datenschutz: {privacy}\n\n"
            "Mit „Akzeptieren“ stimmst du diesen Dokumenten zu."
        ),
        "btn_accept": "✅ Akzeptieren",
        "menu_text": "🥋 ID BJJ — Brazilian Jiu-Jitsu.\n\nWähle einen Bereich 👇",
        "btn_trainer": "🥋 Online-Coach",
        "btn_enc": "📚 BJJ-Enzyklopädie",
        "btn_diet": "🥗 Ernährung",
        "btn_progress": "📈 Mein Fortschritt",
        "btn_oss": "🌐 Oss — soziales Netzwerk (bald)",
        "btn_contact": "✉️ Coach kontaktieren",
        "btn_lang": "🌐 Sprache ändern",
        "lang_changed": "✅ Sprache auf Deutsch umgestellt.",
        "btn_menu": "⬅️ Hauptmenü",
        "btn_cancel": "✖️ Abbrechen",
        "tr_intro": "Fülle einen kurzen Fragebogen aus — der Coach berücksichtigt dein Profil.",
        "tr_q_belt": "🥋 Welchen Gürtel und wie viele Streifen hast du? (z. B.: blau, 2 Streifen)",
        "tr_q_exp": "📅 Wie viele Monate trainierst du BJJ?",
        "tr_q_freq": "🔁 Wie viele Trainings pro Woche?",
        "tr_q_goal": "🎯 Was ist dein Ziel? (z. B. Guard verbessern, Turniervorbereitung, Fitness)",
        "tr_q_injury": "🩹 Einschränkungen oder Verletzungen? (wenn keine — schreibe „nein“)",
        "dt_intro": "Fülle den Fragebogen aus — ich berechne Kalorien und Makros (Mifflin-St Jeor).",
        "dt_q_sex": "⚧ Dein Geschlecht? (männlich / weiblich)",
        "dt_q_age": "🎂 Dein Alter (volle Jahre)?",
        "dt_q_height": "📏 Größe in cm?",
        "dt_q_weight": "⚖️ Gewicht in kg?",
        "dt_q_activity": "🏃 Aktivität: sitzend / leicht / mittel / hoch / sehr hoch?",
        "dt_q_goal": "🎯 Ziel: abnehmen / Muskeln aufbauen / Form halten / Gesundheit / Gewicht machen?",
        "anketa_saved": "✅ Profil gespeichert!",
        "greet_trainer": "🥋 Ich bin dein Online-Coach. Frag mich zu Technik, Trainingsplan, Fortschritt.",
        "btn_comp": "🏆 Wettkampfplan",
        "comp_intro": "🏆 Ich erstelle einen persönlichen Turnier-Vorbereitungsplan. Beantworte 3 Fragen.",
        "comp_q_weeks": "📅 Wie viele Wochen bis zum Wettkampf? (eine Zahl, z. B. 8)",
        "comp_q_format": "🥋 Turnierformat?",
        "cf_gi": "🥋 Gi (mit Kimono)",
        "cf_nogi": "🩳 No-Gi (ohne Kimono)",
        "cf_both": "🔁 Gi + No-Gi",
        "comp_q_goal": "🎯 Ziel für das Turnier? (z. B. gewinnen, Erfahrung sammeln, Spezialtechnik üben)",
        "comp_generating": "⏳ Ich erstelle deinen Vorbereitungsplan…",
        "comp_user_req": "Erstelle meinen Wettkampf-Vorbereitungsplan anhand meines Profils und der Turnierdaten.",
        "btn_journal": "📓 Trainingstagebuch",
        "jr_title": "📓 Trainingstagebuch",
        "jr_empty": "Dein Tagebuch ist leer. Trage dein erstes Training ein — ich merke mir, was du geübt hast, und helfe dir, ein System daraus zu machen.",
        "jr_recent": "Letzte Einträge:",
        "jr_count": "Einträge insgesamt: {n}.",
        "btn_jr_add": "✍️ Training eintragen",
        "btn_jr_review": "📊 Coach-Analyse",
        "jr_ask": "Was hast du heute trainiert? Kurz: Techniken/Positionen, was geklappt hat, woran arbeiten.",
        "jr_saved": "✅ Eingetragen! Schon {n} Trainings im Tagebuch. Komm nach jedem Training wieder 💪",
        "jr_review_wait": "⏳ Ich analysiere dein Tagebuch…",
        "jr_need_entries": "Trage zuerst mindestens ein Training ein — dann analysiere ich.",
        "jr_user_req": "Analysiere mein Trainingstagebuch anhand meines Profils.",
        "btn_jr_plan": "🗺️ Mein Gameplan",
        "jr_plan_wait": "🗺️ Ich erstelle deinen Gameplan aus dem Tagebuch…",
        "jr_plan_req": "Erstelle meinen Gameplan (Spielplan) aus meinem Tagebuch anhand meines Profils.",
        "greet_encyclopedia": "📚 Ich bin die BJJ-Enzyklopädie. Frag mich zu Geschichte, Gürteln, Guards, Techniken, Champions.",
        "greet_dietolog": "🥗 Ich bin der Ernährungsberater des Clubs. Frag mich zu Ernährung, Kalorien, Trainingsessen.",
        "ai_unavailable": "⚠️ Die KI ist gerade nicht verfügbar, versuch es später.",
        "diet_calc": "Berechne meine Kalorien und Makros anhand meines Profils.",
        "contact_ask": "✉️ Worum geht es dir?",
        "ck_trial": "🆓 Probetraining",
        "ck_question": "❓ Frage an den Coach",
        "ck_sub": "💳 Mitgliedschaft / Preise",
        "contact_phone": "Anfrageart: {kind}.\n📞 Hinterlasse deine Telefonnummer — ein Coach meldet sich bei dir.",
        "contact_done": "✅ Anfrage erhalten! Ein Coach meldet sich in Kürze bei dir.",
        "oss_text": (
            "🌐 Oss — das soziale Netzwerk für Grappler\n\n"
            "Wie Instagram, aber für deine Leute: Trainings-Feed, Freunde und Partner, "
            "Gyms weltweit, Austausch von Erfahrungen und Erfolgen.\n\n"
            "🚧 In Entwicklung — bald verfügbar! Verfolge Ankündigungen hier im Bot."
        ),
        "pg_title": "📈 Dein Fortschritt",
        "pg_rank": "Rang",
        "pg_rank_none": "Rang: nicht festgelegt (fülle den „Online-Coach“-Fragebogen aus)",
        "pg_level": "Level",
        "pg_to_next": "Bis zum nächsten Level",
        "pg_hint": "XP gibt es für Fragebögen, KI-Fragen und Anfragen. Komm oft wieder! 💪",
        "btn_share_progress": "📤 Karte teilen",
        "card_level": "Level",
        "share_caption": "🥋 Mein BJJ-Fortschritt: {belt}, {title} (Level {level}). Ich verbessere mein Jiu-Jitsu mit ID BJJ 👉 {url}",
        "btn_invite": "🤝 Freund einladen",
        "invite_text": "🤝 Lade Freunde zu ID BJJ ein!\n\nSchick einem Freund deinen Link — wenn er beitritt, bekommt ihr BEIDE Bonus-XP.\n\nDein Link:\n{link}\n\nEingeladene Freunde: {count}",
        "ref_reward": "🎉 Ein Freund ist über deinen Link zu ID BJJ gekommen! +{xp} XP. Danke, dass du die Community wachsen lässt 🤝",
    },
}


def t(lang: str | None, key: str, **kwargs) -> str:
    lang = lang if lang in T else DEFAULT_LANG
    s = T[lang].get(key) or T[DEFAULT_LANG].get(key, key)
    return s.format(**kwargs) if kwargs else s


def belt_label(belt: str, lang: str | None) -> str:
    lang = lang if lang in LANGS else DEFAULT_LANG
    return BELT_LABELS.get(belt, {}).get(lang, belt)


def level_title(level: int, lang: str | None) -> str:
    lang = lang if lang in LANGS else DEFAULT_LANG
    title = LEVEL_TITLES[lang][0][1]
    for need, name in LEVEL_TITLES[lang]:
        if level >= need:
            title = name
    return title
