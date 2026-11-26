# Compound interest

- [Pretest](#pretest)
- [Simple and compound interest](#simple-and-compound-interest)
- [Growth over n years](#growth-over-n-years)
- [Compounding frequency](#compounding-frequency)
- [Not covered and errata](#not-covered-and-errata)

How to read this note: what the lecturer said and the slides show, in lecture order. Quotes are verbatim, with … for a cut and [ ] for an insertion; (slide N) is the footer number, (mm:ss) the recording time, and note boxes are tutor additions.

## Pretest

<!-- tal:pretest -->
1. You put 1000 in an account at 4% a year and leave it for two years. What does the second year pay if interest is simple, and what if it compounds?

<details><summary>Answer</summary>

40 if simple and 41.60 if it compounds, because compound interest pays the rate on the whole balance, last year's interest included, and not on the deposit alone (slide 1, 1:38–2:12).

</details>

2. One account pays its quoted 6% a year in two instalments. Over a full year, what rate does it really earn, as an effective annual rate?

<details><summary>Answer</summary>

About 6.09%, because the first half-year's interest joins the balance and earns interest in the second half, so the year pays a little more than the quoted rate (slide 3, 10:33–10:55).

</details>

3. A deposit of 500 earns 4% a year, compounded yearly. What does it hold after 4 years?

<details><summary>Answer</summary>

About 584.93, because each of the 4 years multiplies the whole balance, past interest included, by the same 1.04 (slide 2, 5:39–6:14).

</details>
<!-- /tal:pretest -->

## Simple and compound interest

*(slide 1, 0:40–4:39)*

The lecturer starts from one idea that "sits under almost every price in finance" (0:40). A bank pays a yearly rate on a deposit, and slide 1 gives two ways to work out the payment, which differ only in what the rate is paid on (1:04, 2:54).

> Simple: the rate applies to the deposit only
>
> Compound: the rate applies to the balance, past interest included (slide 1)

Under compound interest "last year's interest is now part of the balance, and this year it earns interest too": interest on interest (2:02–2:24). So the first year pays the same both ways, and from the second year compound interest also pays on last year's interest: "The rate is the same, the base is bigger" (3:06–3:54, 4:18).

<!-- tal:check -->
1. Two accounts pay the same yearly rate on the same deposit, one simple and one compound. Why do they hold the same amount after one year but not after two?

<details><summary>Answer</summary>

In the first year there is no past interest yet, so both pay the rate on the deposit; from the second year the compound account also pays it on the first year's interest (3:06–3:54).

</details>
<!-- /tal:check -->

## Growth over n years

*(slide 2, 4:39–9:35)*

### Derivation: the balance after n years

Slide 2 calls the deposit $P$ and the yearly rate $r$ (4:39). The first year gives $P(1+r)$; the second pays the rate on that whole balance, multiplying by $1+r$ again to $P(1+r)^2$ (5:03–5:51). "Every year is the same step … so after n years the balance is P times one plus r to the power n" (6:02):
$$P(1+r)^n \tag{1}$$

*Why does the second year multiply $P(1+r)$, not $P$, by $1+r$?*

<details><summary>Answer</summary>

The rate is paid on the whole balance, not just the deposit, "because last year's interest is in it" (5:39).

</details>

> [!WARNING]
> The most common mistake the lecturer sees is $P(1+nr)$: that is simple interest, and "it forgets that the interest earns interest" (6:48–7:12).

### Worked example: 100 at 5% for 10 years

With 100 at 5% a year for 10 years, simple interest pays 5 a year and ends at 150 (7:36–7:48). Equation (1) gives $100 \times 1.05^{10}$, or 162.89; the lecturer first said 162.98 and corrected it at once (8:00–8:28). The gap widens "because each year starts from a bigger balance" (8:37).

<!-- tal:check -->
1. Take 300 saved at 6% a year with yearly compounding, over 3 years. Year one gives 300 × 1.06 = 318, and year two gives 318 × 1.06 = 337.08. Finish the third year: what is the final balance, and which single power of 1.06 would give it in one step?

<details><summary>Answer</summary>

About 357.30, from 337.08 × 1.06; the same balance is 300 × 1.06 to the power 3 (slide 2, 5:03–6:14).

</details>

2. Someone saves 800 at 3% a year, compounded once a year, for 6 years. Set up and work out the closing balance.

<details><summary>Answer</summary>

About 955.24: 800 × 1.03 to the power 6 (slide 2, 6:02–6:14).

</details>
<!-- /tal:check -->

## Compounding frequency

*(slide 3, 9:35–14:00)*

Many accounts pay monthly or even daily (9:35). With a quoted rate $r$ paid $m$ times a year, "each payment uses r over m", and each payment joins the balance, so the next one earns interest on it (10:09–10:33). Over a year the balance grows by $(1+r/m)^m$, and "take away one and you get the [effective annual rate], the rate you really earn over the year" (10:45–10:55):
$$(1+r/m)^m - 1 \tag{2}$$

On the lecturer's example, 12% a year paid monthly, equation (2) gives about 12.68% (11:19–11:43). Paying more often raises the effective rate "even with the same quoted rate", though monthly to daily adds very little (12:04–12:24). The next lecture asks what a future payment is worth now (13:41).

> [!IMPORTANT]
> Two accounts can quote the same rate and pay different amounts, so "compare their effective annual rates, not the quoted ones" (slide 3, 12:36–12:57).

> [!NOTE]
> Equation (2) at a quoted 12%: twice a year gives $1.06^2 - 1 = 12.36\%$, four times $1.03^4 - 1 \approx 12.55\%$. Why does each extra payment add less?

<!-- tal:check -->
1. You must rank three savings accounts that pay interest on different schedules. Which single number do you work out for each one?

<details><summary>Answer</summary>

Its effective annual rate, since quoted rates on different schedules cannot be compared directly (slide 3, 12:48).

</details>
<!-- /tal:check -->

## Not covered and errata

<!-- tal:not-covered -->
- 0:00–0:40: small talk before the lecture, while people found their seats.
<!-- /tal:not-covered -->

<!-- tal:errata -->
> [!CAUTION]
> Transcript and slide errata
>
> | Time | Heard | Should be |
> |---|---|---|
> | 8:12 | 162.98 | 162.89 (lecturer's slip, corrected) |
> | 10:55 | effect of annual rate | effective annual rate |
<!-- /tal:errata -->
