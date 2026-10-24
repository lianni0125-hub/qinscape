from __future__ import annotations

import json
import random
import re
import threading

POOLS = {
    "xieyi": [
        "雨后的空山，云正在散", "远处有水声穿过竹林", "月光落在无人经过的石阶上",
        "松风由近处缓缓退远", "一叶舟沿春水慢慢远去", "薄雾里偶尔传来一声鹤鸣",
        "让暮色从山脊逐层落下", "保留风停之后的大片留白", "清泉绕过长满青苔的旧石",
        "微雨刚歇，檐下还有余响", "山色很远，灯火只留一点", "让云影与水光彼此回应",
    ],
    "tiaoxin": [
        "我有些悲伤，想先安静一会", "最近心里很乱，希望慢慢稳定", "有点疲惫，想找回一点力量",
        "心里压着火，想让它有地方流动", "有些害怕，希望声音稳稳陪着", "我对一件事很自责，想先松开一点",
        "我像是没什么感觉，想慢慢找回波动", "有些思念放不下，想留一处安放", "心绪太兴奋了，想慢慢收回来",
        "我有些迷茫，希望先听见一个方向", "压力堆得很满，想给自己留出空隙", "我还说不清，只想静静听一会",
    ],
}

CONTEXT = {
    "雨": ["保留雨后的潮湿与静意", "让檐下余响慢慢隐去", "在远处添一线初晴"],
    "山": ["让山色由近处退向远方", "加入若隐若现的空谷回声", "让云雾沿山脊缓缓散开"],
    "月": ["让月色落在更安静的地方", "保留夜深之后的大片留白", "加入一缕很远的风声"],
    "水": ["让水声成为全曲的暗线", "加入一叶缓慢远去的舟", "让波纹一层层归于平静"],
    "悲": ["希望音乐先陪伴，不急着改变", "让哀伤被轻轻承接住", "再慢慢走向可以呼吸的安定"],
    "累": ["先给我稳定的支撑", "不要催促，只恢复一点生机", "让声音温厚而有呼吸"],
    "疲惫": ["先给我稳定的支撑", "不要催促，只恢复一点生机", "让声音温厚而有呼吸"],
    "乱": ["让节奏逐段变得简单", "先承接纷乱，再慢慢收束", "希望最后落在稳定的中心"],
    "焦虑": ["不要突发强音和密集节奏", "让呼吸与速度慢慢下降", "希望声音可预测、可以依靠"],
    "难过": ["先陪我停在这里，不急着转晴", "希望哀意被接住，再慢慢变轻", "保留一点低回，也留一点出口"],
    "伤心": ["先陪我停在这里，不急着转晴", "希望哀意被接住，再慢慢变轻", "保留一点低回，也留一点出口"],
    "孤独": ["希望声音靠近一些，但不要拥挤", "给我一处安静而温暖的回应", "让远处的声部慢慢来到身边"],
    "委屈": ["先承接这份难言，不急着解释", "让紧绷一点点松开，不必强忍", "希望声音温和，却有支撑"],
    "烦": ["让节奏逐段变得简单", "先把拥挤的念头一层层放下", "不要尖锐和突然的声音"],
    "睡不着": ["让声音缓慢、重复而可预测", "不要明显高潮，只留平稳起伏", "希望思绪跟着节奏慢慢变远"],
    "生气": ["先让这股力量有地方流动", "不压住它，也不让它继续升高", "希望节奏有力，但不尖锐"],
    "愤怒": ["先让这股力量有地方流动", "不压住它，也不让它继续升高", "希望节奏有力，但不尖锐"],
    "害怕": ["让声音稳定可预测，不突然逼近", "先给我一个可以停留的中心", "希望远处的声部慢慢靠近"],
    "不安": ["让声音稳定可预测，不突然逼近", "先给我一个可以停留的中心", "希望起伏缓慢而有边界"],
    "自责": ["不急着说服我，先让心绪松一点", "保留反思，但不反复下沉", "希望声音温和而有承托"],
    "后悔": ["让过去被看见，也留一点向前的空间", "不反复强化遗憾", "希望收束时稳稳落下"],
    "麻木": ["不强行振作，只唤回一点微弱波动", "从稳定的低声部慢慢展开", "不要过度热烈或甜美"],
    "空洞": ["先给空白一个可以停留的轮廓", "只加入很微弱的生机", "让声音疏而不冷"],
    "思念": ["让思念有一处安放，不急着告别", "保留远近之间的回应", "希望最后只留一点余温"],
    "压力": ["先把拥挤的层次一点点减掉", "给呼吸和沉默留出位置", "希望声音稳定，不再增加任务感"],
    "迷茫": ["不急着得出答案，先出现一条路", "让旋律从游离慢慢找到中心", "结尾保留开放，但不失去方向"],
    "兴奋": ["保留这份明亮，再慢慢收回呼吸", "不要突然压低，只让节奏逐渐疏开", "希望最后明亮而安定"],
}
SUGGESTION_LLM_LOCK = threading.Lock()
FORBIDDEN_LLM_WORDS = ("您", "你", "我们", "一起", "是否", "为什么", "触发点", "放松方法", "情绪波动", "诊断", "治疗", "听觉", "过滤")


def local_suggestions(mode: str, prompt: str, exclude: list[str] | None = None) -> list[str]:
    blocked = set(exclude or [])
    contextual: list[str] = []
    for keyword, values in CONTEXT.items():
        if keyword in prompt:
            contextual.extend(values)
    contextual = [item for item in dict.fromkeys(contextual) if item not in blocked]
    general = [item for item in POOLS[mode] if item not in blocked and item not in contextual]
    seed = f"{mode}:{prompt}:{len(prompt)}"
    rng=random.Random(seed);rng.shuffle(contextual);rng.shuffle(general)
    # Once the user has revealed a recognisable image or state, keep at least
    # one contextual continuation visible instead of shuffling back to generic
    # starter phrases.
    return [*contextual[:2],*general][:3]


def suggestions(mode: str, prompt: str, exclude: list[str] | None = None) -> dict:
    fallback = local_suggestions(mode, prompt, exclude)
    if len(prompt.strip()) < 4:
        return {"suggestions": fallback, "source": "local"}
    try:
        import torch
        if not torch.cuda.is_available():
            return {"suggestions": fallback, "source": "local"}
        from .llm_adapter import complete
        if not SUGGESTION_LLM_LOCK.acquire(blocking=False):
            return {"suggestions": fallback, "source": "local"}
        instruction = (
            "只输出JSON字符串数组，恰好3项。每项6至22个汉字，是帮助用户继续表达的短句，"
            "不得改写或评价用户，不诊断、不承诺疗效，三项角度不能重复。"
        )
        if mode == "xieyi":
            instruction += "分别从画面、声音、空间运动中延展，保持东方写意与留白；不用技术词。"
        else:
            instruction += "分别从陪伴方式、变化方向、声音边界中补充。必须用可直接续在原文后的第一人称表达；不是心理咨询提问，不用问号。"
        try:
            raw = complete("你是琴境的克制中文提示生成器。", f"{instruction}\n用户已写：{prompt}", 96)
        finally:
            SUGGESTION_LLM_LOCK.release()
        match = re.search(r"\[.*?\]", raw, re.S)
        values = json.loads(match.group(0) if match else raw)
        cleaned = []
        for value in values if isinstance(values, list) else []:
            item = re.sub(r"[\r\n\t]+", "", str(value)).strip(" ，。；、")
            if 6 <= len(item) <= 22 and not any(word in item for word in FORBIDDEN_LLM_WORDS) and "？" not in item and "?" not in item and item not in cleaned and item not in set(exclude or []):
                cleaned.append(item)
        for item in fallback:
            if item not in cleaned:
                cleaned.append(item)
        return {"suggestions": cleaned[:3], "source": "qwen"}
    except Exception:
        return {"suggestions": fallback, "source": "local"}
