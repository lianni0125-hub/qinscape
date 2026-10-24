# 琴境 Skill

这里的 Skill 指“从古琴曲语料中提炼、能被生成系统执行的作曲知识”，不是 Codex Skill。

## 运行顺序

```text
用户输入
  ├─ 写意：意象解析与场景弧线
  └─ 调心：状态评估 → 五音/气机策略 → 场景弧线
               ↓
       shared composition core
  全曲形态 → 段落功能 → 局部母题与节奏动作
               ↓
        generation-neutral plan
```

`generated/` 是语料计算结果；人工文化解释和经过校验的生成规则不能被重新生成过程覆盖。

## 查询示例

```powershell
npm run query -- --mode xieyi --prompt "秋江月夜，先清冷后安定"
npm run query -- --mode tiaoxin --prompt "从烦乱慢慢落到稳定，有水与远山"
npm run plan:tiaoxin -- --prompt "我很悲伤，反复想一件事，希望慢慢稳定"
```

查询结果返回若干“参照曲 Skill”，每条同时包含文化框架、全曲弧线、段落参数和短母题。它是后续提示词规划器或模型适配器的输入，不直接输出 MIDI。

