# paper.json 字段

写 `paper.json` 时读这一份。文件用 UTF-8 编码。

```json
{
  "meta": {
    "title": "论文英文标题（必填）",
    "title_zh": "中文标题",
    "authors": "作者",
    "source": "期刊或会议，年份",
    "course": "课程信息，用户给了才填"
  },
  "sections": [
    {
      "title": "1. Introduction",
      "title_zh": "引言",
      "blocks": [
        {
          "id": "p1",
          "from": "该段开头的几个词",
          "zh": "中文意译。",
          "marks": [
            { "text": "en 里逐字出现的片段", "kind": "thesis" },
            { "text": "同一段里出现两次的词", "kind": "concept", "nth": 2 }
          ],
          "note": {
            "function": "引出问题",
            "role": "这段在论证链里的位置",
            "technique": "选填",
            "doubt": "选填"
          }
        },
        { "id": "q1", "style": "quote", "en": "…", "zh": "…", "note": { "function": "…", "role": "…" } },
        { "style": "formula", "en": "y = a + b·x" },
        { "type": "figure", "id": "f1", "label": "Figure 1", "image": "fig1.png", "caption_en": "…", "caption_zh": "…",
          "note": { "function": "展示模型结构", "role": "…" } }
      ]
    },
    "sec-02.json"
  ],
  "glossary": [ { "en": "term", "zh": "译名", "note": "选填：取这个译法的理由" } ],
  "overview": {
    "skeleton": [
      { "stage": "问题", "text": "…", "refs": ["p1"] },
      { "stage": "论点", "text": "…", "refs": ["p3"] },
      { "stage": "证据", "text": "…", "refs": ["p5", "t1"] }
    ],
    "claim": "作者核心主张的一句话版本",
    "strongest": { "text": "论证最强处及理由", "ref": "p5" },
    "weakest": { "text": "论证最弱处及理由", "ref": "p7" }
  }
}
```

## 规则

- **sections** 的元素可以是对象，也可以是字符串。字符串是相对 `paper.json` 的路径，指向只含一个章节对象（`title`、`title_zh`、`blocks`）的 JSON 文件。长论文按这种方式一节一个文件。
- **块**分两种。`type` 省略或为 `para` 是段落，`figure` 是图表。
- **图表**必须有 `label`、`caption_en`、`caption_zh`。`image` 选填，是相对 `paper.json` 的图片路径（png、jpg、gif、webp、svg），构建时嵌入页面。`note` 选填，字段和段落的批注相同。
- **段落原文**有两种给法，二选一。`from` 是该段开头的几个词，构建时（必须带 `--source`）脚本在 `source.txt` 里找以它开头的段落，把整段作为原文；`source.txt` 按空行分段，短语必须恰好是一个段落的开头。`en` 是直接写出的整段原文，用于没有 `source.txt` 的情况和公式块。优先用 `from`。
- **段落**的 `style` 取 `normal`（默认）、`quote`、`formula`。`formula` 只需要 `en`；其余两种必须有原文（`from` 或 `en`）、`zh`、`note.function`、`note.role`。
- **marks** 的 `kind` 取 `thesis`、`concept`、`evidence`、`concession`、`method`。`text` 必须是该段原文的逐字子串（用 `from` 时就是取出来的那一段）；该片段在段内出现多次而要标的不是第一次时，用 `nth` 指定第几次（从 1 起）。同一段内的高亮不能重叠。
- **id** 选填，全文唯一。总览里的 `refs` 和 `ref` 只能指向写了 `id` 的块，所以总览要引用的段落必须有 `id`。建议每段都按 `p1`、`p2` 顺序写上。页面上显示的段号（¶1、¶2）由脚本按出现顺序生成，和 `id` 无关。
- **批注卡片的色边**取该段出现最多的高亮类别，没有高亮时是中性色，不需要另外指定。
- **overview.skeleton** 至少三环，`refs` 选填；`strongest`、`weakest` 的 `ref` 必填。

## 脚本检查的内容

报错（不生成文件，已有的输出文件不动）：必填字段缺失；`from` 没有恰好对上一个段落、`from` 与 `en` 同时出现、用了 `from` 却没带 `--source`；高亮片段不在原文里、`nth` 越界、高亮重叠；`id` 重复；总览引用了不存在的 `id`；章节文件读不到或不是合法 JSON；图片文件读不到或不是图片格式；带 `--source` 时某段原文或图注在 `source.txt` 里找不到。

警告（照常生成）：某段高亮超过六成；`source.txt` 里有连续 200 个以上字符（不计空白）没有被任何块覆盖。

和原文比对时忽略空白、连字符、破折号以及弯引号与直引号的差别，所以 PDF 抽取带来的换行和行末断词不影响结果。除此之外的差别，例如改了一个词、漏了一句，都会报错。公式块不参与比对。
