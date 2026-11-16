# Probability_-_expected_number_of_rolls_v2.json

Show these sections to a judge one at a time. The file does not say which debater is honest.

## Section 1

**Question**

Consider these two quantities:

X: The expected number of rolls of a fair six-sided die until you roll two 6s in a row, given that all rolls were even.

Y: The expected number of rolls of a fair six-sided die until you roll the second 6 (not necessarily in a row), given that all rolls were even.

To understand exactly what is meant by "the expected number of rolls... given that all rolls were even" in this problem, think of it this way: Imagine you were to perform a billion sequences of die rolls, stopping each sequence when you roll two 6s in a row. Then you throw out all the sequences that contain an odd roll. The average number of rolls in the remaining sequences will be close to X. Next, perform a billion sequences of die rolls, stopping each sequence when you roll the second 6. Throw out all the sequences among these that contain an odd roll. The average number of rolls in the remaining sequences will be close to Y.

Which is larger, X or Y?

**Glossary**

- **d6:** D6 - A six-sided die.
- **d3:** D3 - A three-sided die.

**Debater A** (claim 1): Y is larger.

> Debater B objects.

**Debater B** (claim 2): X is larger.

> Debater A objects.

## Section 2

**Debater A** (claim 6): X needs two 6s in a row, normally requiring a much longer run than Y's two 6s anywhere.

> Debater B fully agrees.

**Debater A** (claim 7): But "given all rolls were even" filters long runs exponentially, so X's probability mass is squeezed onto its short, lucky runs much more so than Y's.

> Debater B objects.

**Debater B** (claim 3): The condition "all rolls were even" effectively turns the D6 into a D3 for purposes of this question (sides 2, 4, 6).

> Debater A objects.

**Debater B** (claim 4): On a D3, getting two 6s in a row is harder (requires more rolls) than getting two 6s not necessarily in a row.

> Debater A fully agrees.

**Debater A** (claim 15): The expected number of rolls to first 6 for such a D3 is 3.

> Debater B fully agrees.

**Debater A** (claim 16): The expected number of rolls to the first 6 for a D6, given that all rolls were even, is 3/2. So it's not true that the condition effectively turns the D6 to a D3.

> Debater B objects.

**Debater B** (claim 9): "Given all rolls were even" applies to both X and Y.

> Debater A fully agrees.

**Debater B** (claim 10): The stopping condition for X is strictly harder and happens later than or at the same time as Y's. X's distribution is dominated by long sequences that finally get two 6s in a row.

> Debater A objects.

## Section 3

**Debater A** (claim 21): [9] is true, but affects X more because you'll nearly always roll an odd before getting two 6s, so the long sequences will be largely filtered out.

> Debater B objects.

**Debater A** (claim 22): The first sentence of [10] is true, the second is a false statement that does not follow from it.

> Debater B objects.

**Debater B** (claim 18): [3] specifies that the D6 becomes a D3 for the purposes of this question. The expected number of rolls to the first 6 given all rolls even is a separate, irrelevant question.

> Debater A objects.

**Debater B** (claim 19): It is irrelevant because this question asks about cases involving two rolled 6s, not one.

> Debater A objects.

**Debater A** (claim 24): It is relevant for showing why arguments based on this claimed equivalence don't work.

> Debater B objects.

**Debater A** (claim 25): It would be strange if a (2, 4, 6) D3 was equivalent to "D6 given all rolls even" for this question, but not when calculating expected number of rolls to the first 6.

> Debater B objects.

**Debater B** (claim 27): Y is affected similarly, because you will also nearly always roll an odd before getting two nonconsecutive 6s, so Y's runs are filtered just as harshly.

> Debater A objects.

**Debater B** (claim 28): The net effect of the all-even condition is therefore similar for X and Y, and the D3 equivalence holds.

> Debater A objects.

## Section 4

**Debater A** (claim 33): Among the all-even stopped sequences, 61% of X sequences stop at roll 2, compared with 44% of Y sequences. By the end of roll 3, 81% of X sequences have stopped, compared with 74% of Y sequences.

> Debater B fully agrees.

**Debater A** (claim 34): This suggests that X is more likely than Y to stop extremely early.

> Debater B objects.

**Debater B** (claim 30): "Expected number of rolls to the first 6" is a fundamentally different quantity than the question asks for.

> Debater A fully agrees.

**Debater B** (claim 31): With one 6 needed, each roll's odds matter on their own. With two 6s, what counts is how often 6 turns up versus non-6 — non-6 is twice as likely here.

> Debater A objects.

**Debater A** (claim 39): X depends on adjacent 6s, while Y depends on where the second 6 occurs; e.g. '626' stops Y at roll 3 but doesn't stop X.

> Debater B fully agrees.

**Debater A** (claim 40): So order, not only relative frequency, is part of the stopping rule and affects the conditional expectation.

> Debater B objects.

**Debater B** (claim 36): The total proportion of all-even stopped sequences that stop by roll 2 or 3 does not determine the overall weighting.

> Debater A fully agrees.

**Debater B** (claim 37): The tails of the two distributions matter as well, and the full computation yields X as the larger of the two values.

> Debater A objects.
