# 复利

- [课前测](#课前测)
- [单利和复利](#单利和复利)
- [多年后的余额](#多年后的余额)
- [计息频率](#计息频率)
- [未讲到的内容和勘误](#未讲到的内容和勘误)

阅读说明：正文只写老师讲过的和课件上有的内容，按讲课顺序排列。引号里是录音或课件的英文原话，… 表示有删节，[ ] 表示补入或更正的词；(slide N) 是课件页脚的页码，(mm:ss) 是录音时间。提示框是辅导者补充的内容，勘误框列出转写稿和课件里的错误。

## 课前测

<!-- tal:pretest -->
1. 小林把 2000 存进银行，年利率 3%，存了两年。第二年的利息按单利算是多少？按复利算又是多少？

<details><summary>答案</summary>

单利 60，复利 61.80：复利第二年按整个余额计息，余额里已经有第一年的 60 元利息 (slide 1, 1:38–2:12)。

</details>

2. 一张信用卡写明名义年利率 18%，欠款按月计息。持卡人一年里实际承担的年利率是多少？

<details><summary>答案</summary>

约 19.56%：每个月的利息都并入欠款，之后每个月连它一起计息，所以一年下来高于名义年利率 (slide 3, 10:33–10:55)。

</details>

3. 账户开户时存入 2500，此后按 4% 的年利率逐年复利。第 2 年年末余额是多少？

<details><summary>答案</summary>

2704：每一年都把整个余额，连同之前的利息，乘上同一个 1.04 (slide 2, 5:39–6:14)。

</details>
<!-- /tal:pretest -->

## 单利和复利

*(slide 1, 0:40–4:39)*

老师开场就说，今天只讲一个概念：复利 (compound interest)。它“sits under almost every price in finance”，储蓄账户、房贷和信用卡账单里都有它，所以值得一次弄清楚 (0:40–1:04)。银行按年利率给存款付息，第一页课件列出了两种算法 (1:04)：

> Simple: the rate applies to the deposit only
>
> Compound: the rate applies to the balance, past interest included (slide 1)

单利 (simple interest) 每年只按本金计息，已经付出的利息“just sits there to one side”，自己不再生息 (1:16–1:28)。复利按整个余额计息，而余额里包括以前挣到的利息，用老师的话说就是“last year's interest is now part of the balance, and this year it earns interest too”(2:02)。老师称这是全部的窍门，人们管它叫“interest on interest”(2:12)。

两种算法用的是同一个利率，变的只是利率所乘的基数 (2:54)。第一年两者完全一样，因为还没有过去的利息；从第二年起，单利照旧只按本金付息，复利却连上一年的利息一起计息，每年多付一点，越积越多 (3:06–4:06)。所以把复利理解成利率更高是不对的，老师的原话是“The rate is the same, the base is bigger”(4:18)。

<!-- tal:check -->
1. 两个账户本金一样、年利率也一样，一个按单利、一个按复利。为什么第一年年底两者余额相同，第二年年底就不同了？

<details><summary>答案</summary>

第一年还没有过去的利息，两者都只按本金计息；从第二年起，复利账户还要按第一年的利息计息 (3:06–3:54)。

</details>
<!-- /tal:check -->

## 多年后的余额

*(slide 2, 4:39–9:35)*

### 推导：n 年后的余额

第二页课件把本金记作 $P$，年利率记作 $r$ (4:39)。老师特意一年一年地推，因为“the reason for each step matters more than the formula”(4:51)。第一年银行付 $rP$ 的利息，余额变成 $P(1+r)$；第二年利率作用在整个余额 $P(1+r)$ 上，于是再乘一次 $1+r$，得到 $P(1+r)^2$；第三年同理得到三次方 (5:03–6:02)。每一年都是同一步：“Every year is the same step … so after n years the balance is P times one plus r to the power n”(6:02)。
$$P(1+r)^n \tag{1}$$

*为什么第二年乘 $1+r$ 的是 $P(1+r)$，而不只是本金 $P$？*

<details><summary>答案</summary>

因为复利按整个余额计息，而这时的余额里已经有第一年的利息。老师说要乘整个余额，“not just the deposit, because last year's interest is in it”(5:39)。

</details>

> [!WARNING]
> 老师说，作业和考试里最常见的错误是把每年的利息直接相加，写成 $P(1+nr)$。这其实是单利：“It forgets that the interest earns interest”(6:48–7:12)。

### 例题：100 按 5% 存 10 年

老师代入的数字是本金 100、年利率 5%、存 10 年 (7:36)。按单利每年得 5，10 年后是 150 (7:48)；按复利要算 $1.05^{10}$，约为 $1.6289$，所以余额是 162.89。老师先说成 162.98，下一句就改了过来 (8:00–8:28)。两者的差距起初很小，后来越拉越大，“because each year starts from a bigger balance”(8:37)：第一年年底都是 105，第二年单利 110、复利 110.25，到第十年差距已接近 13 (8:49–8:59)。

<!-- tal:check -->
1. 本金 200，年利率 4%，按年复利，存 3 年。第一年：200 × 1.04 = 208；第二年：208 × 1.04 = 216.32。请接着算完第三年：最后的余额是多少？它等于 1.04 的几次方乘以 200？

<details><summary>答案</summary>

约 224.97，即 216.32 × 1.04；也就是 200 × 1.04 的 3 次方 (slide 2, 5:03–6:14)。

</details>

2. 本金 1000，年利率 6%，按年复利，存 4 年。列出算式并算出最后的余额。

<details><summary>答案</summary>

约 1262.48：1000 × 1.06 的 4 次方 (slide 2, 6:02–6:14)。

</details>
<!-- /tal:check -->

## 计息频率

*(slide 3, 9:35–14:00)*

最后一个问题是银行多久付一次息，很多账户按月甚至按天付 (9:35)。银行报出的是名义年利率 (quoted rate) $r$，却把它拆成几份在一年里分次付 (9:45)。如果一年付 $m$ 次，“each payment uses r over m”(10:09)；每次的利息都并入余额，下一次就连它一起计息，等于复利得更快 (10:33)。一年下来余额乘上 $(1+r/m)^m$，再“take away one and you get the [effective annual rate], the rate you really earn over the year”(10:45–10:55)，这就是实际年利率 (effective annual rate)：
$$(1+r/m)^m - 1 \tag{2}$$

老师举的例子是名义年利率 12%、按月付息：每月付其十二分之一，算出 $1.01^{12}$ 约为 $1.1268$，减去 1，实际年利率约为 12.68% (11:19–11:43)。付息越频繁，实际年利率越高，“even with the same quoted rate”(12:04)；不过增幅越来越小，从按月改成按天几乎没有差别 (12:24)。

> [!IMPORTANT]
> 两个账户可以报出同样的名义年利率，实际付的钱却不一样 (12:36)。所以比较账户时，贷款也一样，要“compare their effective annual rates, not the quoted ones”(slide 3, 12:48–12:57)。

> [!NOTE]
> 用公式 (2) 算名义年利率 12% 的几种付息频率：一年两次是 $1.06^2-1=12.36\%$，一年四次是 $1.03^4-1\approx 12.55\%$，按月约为 $12.68\%$。为什么付息次数越多，每次增加的幅度反而越小？

下课前，老师请大家回头再看这三页课件，单利和复利、余额公式、计息频率，能用自己的话把每一页说成一句话，就算听懂了 (13:21–13:41)。下一讲会把问题倒过来，问将来的一笔钱放到现在值多少 (13:41)。

<!-- tal:check -->
1. 要给四个付息周期各不相同的存款账户排出高低，你该给每个账户算出哪一个数？

<details><summary>答案</summary>

各自的实际年利率；付息周期不同，名义年利率不能直接比较 (slide 3, 12:48)。

</details>
<!-- /tal:check -->

## 未讲到的内容和勘误

<!-- tal:not-covered -->
- 0:00–0:40：开讲前的寒暄，大家还在找座位。
<!-- /tal:not-covered -->

<!-- tal:errata -->
> [!CAUTION]
> 转写稿和课件勘误
>
> | 时间 | 听到的 | 应为 |
> |---|---|---|
> | 8:12 | 162.98 | 162.89（老师口误，已当场更正） |
> | 10:55 | effect of annual rate | effective annual rate |
<!-- /tal:errata -->
