# chat_logic_zh.py
# -*- coding: utf-8 -*-

INTENT_KEYWORDS = {
    "nurse": ["疼", "痛", "恶心", "想吐", "药", "不舒服", "痒", "出血", "药物", "头晕"],
    "cna": ["水", "冰", "卫生间", "洗澡", "帮助", "打扫", "枕头", "干净"],
    "education": ["问题", "是什么", "怎么", "可以吗", "时候"],
    "urgent": ["紧急", "胸口疼", "不能呼吸", "快来人", "救命"],
}

EDUCATION_RESPONSES = {
    "showering": "通常您可以洗澡，但请先咨询您的护士，看是否有任何限制。",
    "pumping": "您应该每2-3小时使用一次吸奶器，以帮助建立您的奶量。您的护士可以为您联系哺乳顾问。",
}


def classify_message(message):
    message = message.lower()
    for category, keywords in INTENT_KEYWORDS.items():
        if any(keyword in message for keyword in keywords):
            return category
    return "unknown"


def get_education_response(message):
    message = message.lower()
    if "洗澡" in message:
        return EDUCATION_RESPONSES["showering"]
    if "吸奶器" in message or "奶" in message:
        return EDUCATION_RESPONSES["pumping"]

    return "这是一个很好的问题。我会让您的护士过来和您谈谈。"