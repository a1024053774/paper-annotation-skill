# paper-annotation

把一篇英文学术论文做成单个 HTML 文件的双栏批注页，用来看清论文的论证结构。

- **左栏**：英文原文，按核心论点、关键概念、实证证据、让步/反驳、方法论五类高亮；每段下面紧跟中文意译。
- **右栏**：逐段中文批注，写明段落功能、在论证链里的角色，以及值得注意的论证技巧或可疑之处。
- **文末**：论证结构总览，包括全文逻辑骨架、作者主张的一句话版本、论证最强处和最弱处，每一条都能点回对应段落。
- 页面顶部的图例可以单独开关某一类高亮，也可以隐藏译文或批注，只读原文。手机上自动变成单栏。

这个 skill 只在你点名时启用：说"用 paper-annotation 把这篇论文做成双栏批注"，或输入 `/paper-annotation`。

## 和直接用一段提示词相比

| 提示词直接生成 HTML 时的问题 | 这里的做法 |
| --- | --- |
| 论文一长，模型会悄悄跳段、合并段落，或者把后半篇写成摘要 | 模型只写数据（`paper.json`），长论文一节一个文件；脚本拿每一段和原文比对，并列出原文里没被收录的长片段 |
| 原文被顺手改写，高亮的句子和原文对不上 | 英文原文不由模型重打：每段只写开头几个词，脚本从抽取的全文里取整段；高亮必须是原文的逐字片段，对不上构建就失败 |
| 每段都被要求写"潜在漏洞"，于是出现编造的批评 | "可疑之处"是选填项，只在能指到具体句子时写 |
| 高亮越标越多，最后满页是颜色 | 给了五类的判定标准，高亮超过段落六成时脚本警告 |
| 五类维度只适合论证型论文 | 实证型、技术型、综述各有一套对应关系，颜色不变 |
| 每次生成的版式和样式都不一样 | 页面由固定模板生成 |
| 图表、公式、引文、脚注没有说明怎么处理 | 各有约定：图表从 PDF 截成图片嵌入页面并配双语图注，公式原样保留，引文单独成块 |
| 没有课程信息时模型会编一个 | 课程信息选填 |

## 目录

```
paper-annotation/
  SKILL.md                    流程和写作要求
  references/schema.md        paper.json 的字段和脚本检查项
  references/analysis-guide.md  五类高亮的判定标准、体裁对应、常见论证手法
  scripts/build.py            校验并生成 HTML（Python 3，无第三方依赖）
  scripts/figure.py           从 PDF 页面截取图表（需要 poppler）
  assets/template.html        页面模板
  agents/openai.yaml          Codex 配置，关闭隐式触发
examples/sample/              一篇虚构短文的完整样例和生成的页面
examples/ioannidis-2005/      一篇真实论文的完整样例（CC BY 许可，含 2 张图、4 张表）
tests/build_e2e.sh            构建脚本的验收测试
```

## 试一下

```bash
python3 paper-annotation/scripts/build.py examples/sample/paper.json -o examples/sample/sample.html --source examples/sample/source.txt
```

```bash
bash tests/build_e2e.sh
```

`examples/sample/` 里的论文、数据和参考文献都是为演示虚构的。

`examples/ioannidis-2005/` 是 Ioannidis JPA (2005) Why most published research findings are false. PLoS Med 2(8): e124（doi:10.1371/journal.pmed.0020124），© 2005 John P. A. Ioannidis，按 Creative Commons Attribution 许可转载；译文和批注为本仓库所加。打开 `ioannidis-2005.html` 看成品，`gen.py` 是这个例子专用的辅助脚本，用来把 PDF 抽取的文本按阅读顺序重排成一段一行的 `source.txt`；各节 JSON 里的段落只写 `from`，没有手打的英文。

## 限制

- 核对脚本只保证收录的段落逐字出自 `source.txt`，并报告没有收录的部分。译文是否准确、批注是否到位，脚本不检查。
- `source.txt` 从 PDF 抽取，抽取本身出错（公式、双栏串行、扫描件）时需要先对照 PDF 修正。
- 字体从 Google Fonts 加载，离线时回退到系统字体。

## 许可

skill 本身（说明、脚本、模板、测试）按 [MIT](LICENSE) 许可。`examples/ioannidis-2005/` 中的论文原文和图表按 Creative Commons Attribution 许可转载，出处见上文。
