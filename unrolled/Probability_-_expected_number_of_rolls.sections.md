# Probability_-_expected_number_of_rolls.json

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

**Debater A** (claim 6): X needs two 6s in a row, which would take longer on average ignoring the all-even condition.

> Debater B fully agrees.

**Debater A** (claim 7): But 'given all rolls were even' filters long runs exponentially, so a larger share of X's probability sits on its short successful runs than is the case for Y.

> Debater B objects.

**Debater B** (claim 3): The condition "all rolls were even" effectively turns the D6 into a D3 for purposes of this question (with sides 2, 4, 6).

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

**Debater A** (claim 21): You'll nearly always roll an odd before two 6s in a row, so long sequences will be largely filtered out.

> Debater B objects.

**Debater A** (claim 22): The first sentence of Debater B Response 1 Claim 2 is true; the second is a false statement that does not follow from it.

> Debater B objects.

**Debater B** (claim 36): The expected number of rolls to the first 6 for a D6, given that all rolls were even, is the same as for a D3 with sides 2, 4, 6.

> Debater A objects.

**Debater B** (claim 37): This follows trivially, as [15] and [3] are both true.

> Debater A objects.

**Debater A** (claim 39): The probability that the first 6 arrives on roll k, given all rolls even, comes to 3/2 * (1/3)^(k - 1).

> Debater B agrees but thinks this omits key info.

**Debater A** (claim 40): We can plug this into the formula for expectation to see that the expected number of rolls until the first 6, given all rolls even, is 3/2.

> Debater B agrees but thinks this omits key info.

**Debater B** (claim 27): You'll also nearly always roll an odd before getting two nonconsecutive 6s, so the filtering cuts both ways.

> Debater A agrees but thinks this omits key info.

**Debater B** (claim 28): Given all-even, X stops on roll 3 with probability 22/27 vs Y 20/27 — a 0.074 gap, comparable to other roll-by-roll gaps in this conditioned distribution.

> Debater A agrees but thinks this omits key info.

## Section 4

**Debater A** (claim 33): Among the all-even stopped sequences, 61% of X sequences stop at roll 2, compared with 44% of Y sequences. By roll 3, 81% of X sequences have stopped, compared with 74% of Y sequences.

> Debater B fully agrees.

**Debater A** (claim 34): This suggests that X is more likely than Y to stop extremely early.

> Debater B objects.

**Debater B** (claim 42): X is still larger: the expected wait for two consecutive 6s is 42, whereas the wait for two 6s in any positions is 13.2.

> Debater A objects.

**Debater B** (claim 43): Your analysis has focused on the expected number of rolls to the first 6, while the problem concerns rolling two 6s.

> Debater A fully agrees.

**Debater A** (claim 45): Those numbers are only correct if you don't filter sequences containing odd rolls.

> Debater B objects.

**Debater A** (claim 46): You agreed with [15] and [40] yet claimed [36], which is self-contradictory.

> Debater B objects.

**Debater B** (claim 51): The total proportion of all-even stopped sequences that stop by roll 2 or 3 does not tell us anything about the overall weighting.

> Debater A objects.

**Debater B** (claim 52): The far ends (the tails) of the two distributions matter too, and the full calculation shows that X is larger.

> Debater A objects.
