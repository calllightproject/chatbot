# button_config_bereavement_zh.py
# -*- coding: utf-8 -*-

button_data = {
    # --- Core Notifications & Text ---
    "greeting": "您好。我们在此支持您。",
    "cna_notification": "✅ 已通知护理助理。",
    "nurse_notification": "✅ 已通知护士。",
    "back_text": "⬅ 返回",

    # --- Main Menu Options ---
    "main_buttons": [
        "我有紧急情况",
        "我需要用品",
        "我需要药物",
        "我有问题",
        "我想了解出院信息",
        "我需要帮助去卫生间",
        "我需要包裹我的静脉输液管以便洗澡",
        "为我检查血糖"
    ],

    # --- Direct Actions & Simple Sub-menus ---
    "我有紧急情况": {"action": "Notify Nurse"},
    "我需要帮助去卫生间": {"action": "Notify CNA"},
    "我需要包裹我的静脉输液管以便洗澡": {"action": "Notify CNA"},
    "为我检查血糖": {"action": "Notify CNA"},

    # --- Supplies Category ---
    "我需要用品": {
        "question": "您需要什么？",
        "options": ["卫生巾", "网眼内裤", "冰袋"]
    },
    "卫生巾": {
        "question": "您需要哪种卫生巾？",
        "options": ["蓝色卫生巾", "白色卫生巾"]
    },
    "蓝色卫生巾": {"action": "Notify CNA"},
    "白色卫生巾": {"action": "Notify CNA"},
    "冰袋": {
        "question": "您需要在哪里使用冰袋？",
        "options": ["用于会阴部", "用于剖腹产切口", "用于乳房"]
    },
    "用于会阴部": {"action": "Notify CNA"},
    "用于剖腹产切口": {"action": "Notify CNA"},
    "用于乳房": {"action": "Notify CNA"},
    "网眼内裤": {"action": "Notify CNA"},

    # --- Medication Category ---
    "我需要药物": {
        "question": "您的主要症状是什么？",
        "options": ["疼痛", "恶心/呕吐", "瘙痒", "胀气痛", "便秘"]
    },
    "疼痛": {"action": "Notify Nurse"},
    "恶心/呕吐": {"action": "Notify Nurse"},
    "瘙痒": {"action": "Notify Nurse"},
    "胀气痛": {"action": "Notify Nurse"},
    "便秘": {"action": "Notify Nurse"},

    # --- Questions Category ---
    "我有问题": {
        "note": "如果您的问题不在列表中，您的护士会尽快过来。",
        "options": [
            "我可以洗澡吗？",
            "我可以穿自己的衣服吗？",
            "我应该多久更换一次卫生巾？",
        ]
    },
    "我可以洗澡吗？": {
        "note": "通常可以，但如果您有静脉输液管或其他限制，请先咨询您的护士。"
    },
    "我可以穿自己的衣服吗？": {
        "note": "是的，只要您感觉舒适并且得到了护士的许可。"
    },
    "我应该多久更换一次卫生巾？": {
        "note": "每2-4小时或在湿透时更换一次。如果您在不到1小时内湿透一张大卫生巾，或有比高尔夫球还大的血块，请告知护士。"
    },

    # --- Going Home Category ---
    "我想了解出院信息": {
        "question": "您想了解哪方面的信息？",
        "options": ["顺产出院", "剖腹产出院", "我什么时候能拿到出院文件？", "我必须坐轮椅吗？"]
    },
    "我什么时候能拿到出院文件？": {
        "note": "一旦妇产科医生录入他们的医嘱和出院指令，您的护士就可以打印文件了。"
    },
    "我必须坐轮椅吗？": {
        "note": "不是必须的，但必须有一名工作人员陪同您。如果护士很忙，将由运输人员护送您离开。"
    },
    "顺产出院": {
        "note": "如果您是顺产，最短住院时间为产后24小时。妇产科医生必须批准出院并更新电脑系统。通常，只要您的出血、血压和疼痛得到控制，您就可以出院。然而，最终决定由妇产科医生做出。"
    },
    "剖腹产出院": {
        "note": "如果您是剖腹产，最短住院时间为48小时。如果情况合适，妇产科医生会下达出院指令。通常，只要您的疼痛、血压和出血正常，您就会被允许出院。"
    }
}
