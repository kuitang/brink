# Brinksmanship: A Game-Theoretic Strategy Simulation

## Authoritative Game Manual v2.0

---

## Foundational Principles

This game is built on five inviolable design principles:

1. **Joint Investment Creates Value**: Mutual cooperation creates a surplus pool that didn't exist before. This is not zero-sum—the pie can grow.

2. **Surplus Requires Settlement**: The cooperation surplus is only distributed through negotiated settlement. If the game ends without agreement, accumulated surplus is lost. This creates genuine incentive to negotiate.

3. **Pure Game-Theoretic Matrices**: Every strategic interaction uses classic 2×2 game theory matrices with real strategic dilemmas.

4. **Symmetric Mechanisms**: If an action destabilizes the situation, BOTH players face increased uncertainty. Variance is shared.

5. **Uncertain Endpoints**: The game has no known final turn. Backward induction cannot operate because any turn might be the last.

---

## Part I: Theoretical Foundations

### 1.1 Core Game Theory

**John Nash (1950)**: Nash Equilibrium—a strategy profile where no player can unilaterally improve their outcome.

**Robert Axelrod (1984)**: *The Evolution of Cooperation* showed that cooperative strategies outperform in repeated games when the "shadow of the future" is long enough.

**Thomas Schelling (1960)**: *The Strategy of Conflict* introduced focal points, tacit bargaining, and the paradox of commitment.

**Kreps et al. (1982)**: Proved that uncertainty about opponent type can sustain cooperation even in finite games.

### 1.2 The Positive-Sum Innovation

Traditional game theory models like Prisoner's Dilemma are **zero-sum in outcomes**—one player's gain is another's loss. This leads to the "chicken" metagame: cooperate initially, then defect before your opponent does.

Brinksmanship uses **Joint Investment** dynamics inspired by Schelling's insight that real negotiations often involve **expanding the pie** through creative solutions. Cooperation isn't just about reducing risk—it creates new value that benefits both parties.

---

## Part II: The 14 Strategic Game Types

The game employs 14 distinct matrix types across 5 categories:

### Category A: Dominant Strategy Games

| Game | Nash Equilibrium | Strategic Character |
|------|-----------------|---------------------|
| **Prisoner's Dilemma** | (Defect, Defect) | Defection dominates but mutual cooperation is better |
| **Deadlock** | (Defect, Defect) | Both prefer mutual defection |
| **Harmony** | (Cooperate, Cooperate) | Cooperation dominates |

### Category B: Anti-Coordination Games

| Game | Nash Equilibria | Strategic Character |
|------|----------------|---------------------|
| **Chicken** | (C,D) and (D,C) | Worst outcome is mutual defection (crash) |
| **Volunteer's Dilemma** | Mixed | Someone must sacrifice |
| **War of Attrition** | Mixed | Continuous commitment contest |

### Category C: Coordination Games

| Game | Nash Equilibria | Strategic Character |
|------|----------------|---------------------|
| **Pure Coordination** | (C,C) and (D,D) | Both prefer matching |
| **Stag Hunt** | (C,C) and (D,D) | Trust vs. safety |
| **Battle of the Sexes** | (C,D) and (D,C) | Coordinate with distributional conflict |
| **Leader** | Asymmetric | One leads, one follows |

### Category D: Zero-Sum & Information Games

| Game | Nash Equilibrium | Strategic Character |
|------|-----------------|---------------------|
| **Matching Pennies** | Mixed only | Pure conflict |
| **Inspection Game** | Mixed | Verify vs. trust |
| **Reconnaissance** | Mixed | Information gathering as escalation |
| **Security Dilemma** | Same as PD | Spiral dynamics |

---

## Part III: Game State & Mechanics

### 3.1 State Variables

```
PLAYER STATE (Hidden)
├── Position_A (0-10): Player A's relative advantage
├── Position_B (0-10): Player B's relative advantage
├── Surplus_Captured_A: VP captured by A through exploitation/settlement
└── Surplus_Captured_B: VP captured by B through exploitation/settlement

SHARED STATE (Visible)
├── Cooperation_Surplus (0-∞): Joint value pool from mutual cooperation
├── Cooperation_Score (0-10): Relationship trajectory
├── Cooperation_Streak: Consecutive CC outcomes
├── Stability (1-10): Behavioral predictability
├── Risk_Level (0-10): Escalation measure
└── Turn (1 to Max): Current turn (Max is hidden, 12-16)
```

### 3.2 Action Classification

All actions are classified as either:
- **Cooperative (C)**: De-escalate, Hold, Propose Settlement, Back Channel, Concede
- **Competitive (D)**: Escalate, Aggressive Pressure, Ultimatum, Show of Force, Demand

### 3.3 Turn Structure

Each turn follows 8 phases:

1. **BRIEFING**: Display narrative and shared state (including surplus)
2. **DECISION**: Both players simultaneously select actions
3. **RESOLUTION**: Resolve via matrix game or special game
4. **STATE UPDATE**: Apply outcome effects (see 3.4)
5. **CHECK DETERMINISTIC ENDINGS**: Risk=10 or Position=0
6. **CHECK CRISIS TERMINATION**: Turn ≥ 10 and Risk > 7
7. **CHECK NATURAL ENDING**: Turn = Max_Turn
8. **ADVANCE**: Increment turn counter

### 3.4 Outcome Effects: The Joint Investment Model

All numerical parameters below are **tunable** - see Appendix C for parameter definitions, tuning guidance, and simulation requirements.

**CC Outcome (Mutual Cooperation)**:
```python
# Create new surplus - scales with cooperation streak
new_surplus = SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * cooperation_streak)
cooperation_surplus += new_surplus
cooperation_streak += 1

# Position unchanged (no zero-sum shift)
# Risk decreases (situation safer)
risk_level -= CC_RISK_REDUCTION

# Cooperation score improves
cooperation_score += 1
```

**CD Outcome (A Cooperates, B Defects)**:
```python
# B captures portion of accumulated surplus
captured = cooperation_surplus * CAPTURE_RATE
surplus_captured_b += captured
cooperation_surplus -= captured

# Plus traditional position shift
position_b += EXPLOIT_POSITION_GAIN
position_a -= EXPLOIT_POSITION_GAIN

# Streak resets
cooperation_streak = 0

# Risk increases
risk_level += EXPLOIT_RISK_INCREASE
```

*Note: If simulation shows late-defection dominance, add streak protection. See Appendix C.*

**DC Outcome**: Mirror of CD (A captures surplus, A gains position)

**DD Outcome (Mutual Defection)**:
```python
# Surplus is partially destroyed (deadweight loss)
cooperation_surplus *= (1.0 - DD_BURN_RATE)

# Position unchanged (no winner)
# Streak resets
cooperation_streak = 0

# Risk spikes
risk_level += DD_RISK_INCREASE

# Cooperation score decreases
cooperation_score -= 1
```

### 3.5 Key Insight: Why This Isn't Zero-Sum

In the traditional zero-sum model:
- CC: Neither gains position
- CD/DC: Exploiter gains what victim loses
- DD: Neither gains position

The only way to "get ahead" is exploitation, leading to chicken dynamics.

In the Joint Investment model:
- **CC creates new value** that didn't exist before
- **CD/DC captures existing surplus** (tempting but limited)
- **DD destroys surplus** (both lose)

This means:
- Sustained cooperation builds a large surplus pool
- Exploitation captures some surplus but resets the streak
- The question becomes: "When do we settle to lock in our joint gains?"

---

## Part IV: Scoring & Victory

### 4.1 Final VP Calculation

At game end, Victory Points are calculated:

```python
# Base VP from position ratio (traditional)
total_position = position_a + position_b
base_vp_a = (position_a / total_position) * 100

# Add captured surplus (from exploitation or settlement)
final_vp_a = base_vp_a + surplus_captured_a
final_vp_b = base_vp_b + surplus_captured_b

# Total VP can exceed 100 if surplus was created and captured!
```

### 4.2 Settlement: The Only Way to Secure Surplus

**Critical Rule**: The cooperation_surplus pool is ONLY distributed through settlement.

If the game ends without settlement:
- Remaining surplus is **LOST** (neither player gets it)
- Only captured surplus (from exploitation) counts

This creates powerful incentive to negotiate:
- A large surplus pool means both players want settlement
- But settlement terms are contested (who gets what share?)

### 4.3 Settlement Protocol

Available after Turn 4 (unless Stability ≤ 2):

1. **Propose**: Offer VP split + surplus split + argument text
2. **Response**: ACCEPT / COUNTER / REJECT
3. **If Counter**: Original proposer: ACCEPT / FINAL_OFFER
4. **If Final Offer**: ACCEPT / REJECT only (no counter)
5. **Max 3 exchanges**, then automatic REJECT
6. **Each REJECT adds escalating risk penalty** (see below)

**Rejection Penalty (Escalating)**:
```python
# Rejection penalties escalate - failed negotiations are costly
# exchange_number: 1st rejection, 2nd rejection, 3rd rejection
risk_penalty = REJECTION_BASE_PENALTY * (1.0 + REJECTION_ESCALATION * (exchange_number - 1))

# With defaults (base=1.5, escalation=0.5):
# 1st rejection: Risk +1.5
# 2nd rejection: Risk +2.25
# 3rd rejection: Risk +3.0 (plus automatic end of negotiation)
```

This escalating penalty creates pressure to reach agreement - repeated rejections dramatically increase crisis probability.

Settlement constraints:
```
Position_Diff = Your_Position - Opponent_Position
Coop_Bonus = (Cooperation_Score - 5) × 2

Suggested_VP = 50 + (Position_Diff × 5) + Coop_Bonus
Valid_Range = [max(20, Suggested - 10), min(80, Suggested + 10)]

Surplus_Split: Negotiable (proposer offers percentage)
```

### 4.4 Multi-Criteria Scorecard

At game end, players see an educational scorecard:

```
═══════════════════════════════════════════════════════
                    GAME RESULTS
═══════════════════════════════════════════════════════

PERSONAL SUCCESS                           PLAYER A  PLAYER B
───────────────────────────────────────────────────────
Final VP                                      72        68
VP Share                                     51.4%    48.6%

JOINT SUCCESS                                  BOTH
───────────────────────────────────────────────────────
Total Value Created                           140 VP
Value vs Zero-Sum Baseline                   +40 VP
Pareto Efficiency                            87.5%
Settlement Reached?                            Yes
Surplus Distributed                          24 VP

STRATEGIC PROFILE                          PLAYER A  PLAYER B
───────────────────────────────────────────────────────
Cooperation Streak (max)                        6         6
Times Exploited                                 1         2
Settlement Initiated By                    Player A      -
═══════════════════════════════════════════════════════
```

### 4.5 Deterministic Endings

**Risk = 10 (Mutual Destruction)**:
- Both players receive **0 VP** (worst possible outcome)
- All surplus is lost
- Game ends immediately
- This is the ultimate punishment - total loss for both players

**Position = 0 (Elimination)**:
- Eliminated player receives 10 VP
- Surviving player receives 90 VP + all their captured surplus
- Remaining cooperation surplus is lost

### 4.6 Probabilistic Endings

**Crisis Termination** (Turn ≥ 10, Risk > 7):
```
P(termination) = (Risk - 7) × 0.08

Risk 8:  8% per turn
Risk 9:  16% per turn
Risk 10: Automatic mutual destruction
```

When crisis termination triggers, final VP is calculated per 4.1.

**Natural Ending** (Turn = Max_Turn):
- Max_Turn is hidden (12-16 range)
- Final VP calculated per 4.1
- Prevents backward induction

---

## Part V: Stability & Consistency

### 5.1 Stability Update Formula

Stability tracks behavioral predictability:

```python
# Decay toward neutral
new_stability = stability * 0.8 + 1.0

# Consistency bonus/penalty based on action switches
switches = count_switches(previous_actions, current_actions)

if switches == 0:    # Both consistent
    new_stability += 1.5
elif switches == 1:  # One switched
    new_stability -= 3.5
else:                # Both switched
    new_stability -= 5.5

# Clamp to valid range
new_stability = clamp(new_stability, 1.0, 10.0)
```

### 5.2 Why Stability Matters

High stability (predictable behavior):
- Lower variance in final VP resolution
- Settlement available
- Signal of trustworthiness

Low stability (erratic behavior):
- Higher variance (chaotic outcomes)
- Settlement blocked if Stability ≤ 2
- Signal of unpredictability

### 5.3 The "Fake Cooperator" Penalty

The decay-based system punishes late-game exploitation:

```
Trajectory: Cooperate 8 turns, then defect
  After Turn 8: Stability = 10.0
  After Turn 9 (defect): Stability ≈ 5.5

Result: The defector faces high variance exactly when trying to lock in gains.
```

---

## Part VI: Variance & Final Resolution

### 6.1 Symmetric Variance Principle

**Core Rule**: Variance affects BOTH players equally based on shared game state.

There is no mechanism where one player faces more uncertainty than another. If the situation is chaotic, both players face chaotic outcomes.

### 6.2 Variance Formula

```python
Base_σ = 8 + (Risk_Level × 1.2)           # Range: 8-20
Chaos_Factor = 1.2 - (Cooperation_Score / 50)  # Range: 1.0-1.2
Instability_Factor = 1 + (10 - Stability) / 20  # Range: 1.0-1.45
Act_Multiplier = {Act I: 0.7, Act II: 1.0, Act III: 1.3}

Shared_σ = Base_σ × Chaos_Factor × Instability_Factor × Act_Multiplier
```

Expected variance ranges:
- Peaceful early game: ~10
- Neutral mid-game: ~19
- Tense late game: ~27
- Chaotic crisis: ~37

### 6.3 Final Resolution

When game ends (not by settlement):

```python
# Calculate expected VP from position
total_pos = position_a + position_b
ev_a = (position_a / total_pos) * 100
ev_b = 100 - ev_a

# Apply symmetric noise
noise = gaussian(0, shared_σ)
vp_a_raw = ev_a + noise
vp_b_raw = ev_b - noise  # Same noise affects both!

# Clamp and add captured surplus
vp_a = clamp(vp_a_raw, 5, 95) + surplus_captured_a
vp_b = clamp(vp_b_raw, 5, 95) + surplus_captured_b
```

---

## Part VII: Balance Testing

### 7.1 Dual-Metric Evaluation

The game uses dual metrics to prevent dominant strategies:

**Primary Metric**: Total Value Created
```
Total_Value = VP_A + VP_B
```

**Secondary Metric**: VP Share
```
Share_A = VP_A / Total_Value
```

### 7.2 Dominant Strategy Test

A strategy is **dominant** (and the game is imbalanced) if:
```
Avg_Total_Value > 120 AND Avg_VP_Share > 55%
```

This means: you can either grow the pie OR capture a larger share, but not both consistently. Strategies that grow the pie tend toward even splits; strategies that exploit tend toward smaller pies.

### 7.3 Pass Criteria

- No strategy achieves >120 total value AND >55% share
- VP variance in 10-40 range
- Settlement rate 30-70%
- Average game length 8-16 turns

---

## Part VIII: Scenario Structure

### 8.1 Three-Act Framework

**Act I (Turns 1-4)**: Opening postures, early signaling
- Stakes multiplier: 0.7×
- Settlement not yet available

**Act II (Turns 5-8)**: Main negotiation phase
- Stakes multiplier: 1.0×
- Settlement becomes available (Turn 5+)

**Act III (Turns 9+)**: Crisis resolution
- Stakes multiplier: 1.3×
- Crisis termination possible (if Risk > 7)

### 8.2 Scenario Themes

Each scenario specifies a visual theme:
- `cold-war`: 1960s government aesthetic
- `renaissance`: Medici-era parchment
- `byzantine`: Imperial purple
- `corporate`: Modern minimal
- `default`: Kingdom of Loathing inspired

---

## Appendix A: Quick Reference

### Outcome Effects Summary

| Outcome | Surplus | Position | Risk | Streak |
|---------|---------|----------|------|--------|
| CC | +SURPLUS_BASE×(1+STREAK_BONUS×streak) | 0, 0 | -CC_RISK_REDUCTION | +1 |
| CD | -(CAPTURE_RATE×protection_factor) captured by B | -0.7, +0.7 | +EXPLOIT_RISK | reset |
| DC | -(CAPTURE_RATE×protection_factor) captured by A | +0.7, -0.7 | +EXPLOIT_RISK | reset |
| DD | -(DD_BURN_RATE) burned | 0, 0 | +DD_RISK | reset |

*See Appendix C for parameter values and tuning guidance.*

### Settlement Constraints

| Condition | Requirement |
|-----------|-------------|
| Available | Turn ≥ 5 |
| Blocked | Stability ≤ 2 |
| VP Range | 20-80 |
| Max Exchanges | 3 |
| Rejection Penalty | Risk +1.5 (escalating) |

### Ending Conditions

| Condition | Result |
|-----------|--------|
| Risk = 10 | **Both get 0 VP** (mutual destruction - worst outcome) |
| Position = 0 | Eliminated: 10 VP, Winner: 90 VP |
| Crisis Termination | Normal resolution |
| Max Turn | Normal resolution |
| Settlement | Agreed VP + surplus split |

---

## Appendix B: Bibliography

**Core Game Theory**
- Nash, J. (1950). "Equilibrium Points in N-Person Games"
- Axelrod, R. (1984). *The Evolution of Cooperation*
- Kreps et al. (1982). "Rational Cooperation in the Finitely Repeated Prisoners' Dilemma"

**Strategic Studies**
- Schelling, T. (1960). *The Strategy of Conflict*
- Schelling, T. (1966). *Arms and Influence*
- Jervis, R. (1978). "Cooperation Under the Security Dilemma"
- Kahn, H. (1965). *On Escalation*

**International Relations**
- Waltz, K. (1979). *Theory of International Politics*
- Mearsheimer, J. (2001). *The Tragedy of Great Power Politics*

**Classical Strategy**
- Machiavelli, N. (1513). *The Prince*
- Clausewitz, C. (1832). *On War*

---

## Appendix C: Tunable Parameters

**IMPORTANT**: These parameters are NOT fixed constants. They should be tuned through simulation to achieve balanced gameplay. Each parameter includes analysis notes and tuning guidance.

**Implementation**: All parameters are defined in `src/brinksmanship/parameters.py`. This file is the single source of truth for game balance constants. Agents and developers should modify this file when tuning balance.

### C.1 Surplus Creation Parameters

```python
# ═══════════════════════════════════════════════════════════════════════════
# SURPLUS_BASE: VP created per mutual cooperation (CC outcome)
# ═══════════════════════════════════════════════════════════════════════════
# Current: 2.0
#
# ANALYSIS: With 14-turn max game and perfect cooperation:
#   - No streak bonus: 14 × 2.0 = 28 VP total surplus
#   - With streak bonus: ~45 VP total surplus (see SURPLUS_STREAK_BONUS)
#   - This is significant vs 100 VP position baseline but not overwhelming
#
# TUNING GUIDANCE:
#   - If settlement rate too LOW: increase (more surplus = more to negotiate over)
#   - If exploitation too WEAK: increase (bigger pool = bigger captures)
#   - If total value > 150 average: decrease (pie growing too fast)
#   - Run: "surplus creation sweep" simulation varying 1.5 to 3.0
#
SURPLUS_BASE = 2.0

# ═══════════════════════════════════════════════════════════════════════════
# SURPLUS_STREAK_BONUS: Additional surplus per streak level
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.1 (10% bonus per consecutive CC)
#
# ANALYSIS: Creates compounding value for sustained cooperation
#   Streak 0:  2.0 VP,  Streak 5:  3.0 VP,  Streak 10: 4.0 VP
#   This rewards patience but creates "when to defect" tension
#
# TUNING GUIDANCE:
#   - If late-game too static: increase (more reward for holding out)
#   - If early defection never happens: decrease (reduce late-game bonus)
#   - Should interact with STREAK_PROTECTION_RATE (see below)
#   - Run: "streak bonus sensitivity" simulation at 0.05, 0.1, 0.15
#
SURPLUS_STREAK_BONUS = 0.1
```

### C.2 Exploitation Parameters

```python
# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE_RATE: Fraction of surplus captured on exploitation (CD/DC)
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.4 (40% of pool)
#
# ANALYSIS: This is the TEMPTATION payoff in game theory terms.
#   - Too high: exploitation always dominates (chicken dynamics)
#   - Too low: no reason to ever defect (boring cooperation fest)
#   - 40% means you need 2-3 exploitations to drain the pool
#   - With ~20 surplus at turn 8, capture = 8 VP (significant but not dominant)
#   - With ~45 surplus at turn 14, capture = 18 VP (very strong)
#
# TUNING GUIDANCE:
#   - If "always cooperate" dominates: increase toward 0.5
#   - If "always defect" dominates: decrease toward 0.3
#   - If "late defection" dominates: add STREAK_PROTECTION (see C.6)
#   - Run: "exploitation timing analysis" simulation
#
CAPTURE_RATE = 0.4

# ═══════════════════════════════════════════════════════════════════════════
# EXPLOIT_POSITION_GAIN: Position shift on exploitation
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.7
#
# ANALYSIS: Zero-sum position transfer (exploiter +0.7, victim -0.7)
#   - Affects final VP calculation: (position / total_position) × 100
#   - Starting positions are 5.0/5.0, so ±0.7 is a 7% shift
#
# TUNING GUIDANCE:
#   - If exploitation feels weak: increase toward 1.0
#   - If one defection is decisive: decrease toward 0.5
#   - Position matters less if surplus is large (settlement dominates)
#
EXPLOIT_POSITION_GAIN = 0.7
```

### C.3 Risk Parameters

```python
# ═══════════════════════════════════════════════════════════════════════════
# CC_RISK_REDUCTION: Risk decrease on mutual cooperation
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.5
#
# ANALYSIS: Cooperation de-escalates. Starting risk is 2.0.
#   - 4 consecutive CCs bring risk to 0 (safe)
#   - Creates breathing room for negotiation
#
# TUNING GUIDANCE:
#   - If crisis termination too frequent: increase (faster de-escalation)
#   - If risk feels meaningless: decrease
#
CC_RISK_REDUCTION = 0.5

# ═══════════════════════════════════════════════════════════════════════════
# EXPLOIT_RISK_INCREASE: Risk increase on exploitation (CD/DC)
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.8
#
# ANALYSIS: Exploitation is risky but not catastrophic.
#   - From starting risk 2.0, need ~10 exploitations to hit risk=10
#   - But mixed with DD outcomes, escalation is faster
#
# TUNING GUIDANCE:
#   - If exploitation feels too safe: increase toward 1.2
#   - If exploitation feels too punishing: decrease toward 0.5
#
EXPLOIT_RISK_INCREASE = 0.8

# ═══════════════════════════════════════════════════════════════════════════
# DD_RISK_INCREASE: Risk increase on mutual defection
# ═══════════════════════════════════════════════════════════════════════════
# Current: 1.8
#
# ANALYSIS: Mutual defection is DANGEROUS - the stick in the game.
#   - From starting risk 2.0, only 4-5 DDs to hit risk=10 (mutual destruction)
#   - This makes DD the worst outcome for both players (Chicken logic)
#   - Mutual destruction = 0 VP for BOTH players (total loss)
#
# TUNING GUIDANCE:
#   - TARGET: Mutual destruction rate should be 10-20% of games
#   - If MD rate > 20%: decrease toward 0.8
#   - If MD rate < 10%: increase toward 1.2
#   - Current default (1.0) calibrated for ~10% MD rate with settlement >= 70%
#   - Reduced from 1.8 to give more time for settlement/de-escalation
#   - Remember: MD is now 0,0 VP (worst outcome) - players should fear it
#
DD_RISK_INCREASE = 1.0

# ═══════════════════════════════════════════════════════════════════════════
# DD_BURN_RATE: Fraction of surplus destroyed on mutual defection
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.2 (20% destroyed)
#
# ANALYSIS: Deadweight loss from conflict - value destroyed, not captured.
#   - 3 DDs destroy ~50% of accumulated surplus
#   - Creates strong incentive to avoid DD even when not cooperating
#
# TUNING GUIDANCE:
#   - If players don't fear DD enough: increase toward 0.3
#   - If surplus disappears too fast: decrease toward 0.15
#
DD_BURN_RATE = 0.2
```

### C.4 Settlement Parameters

```python
# ═══════════════════════════════════════════════════════════════════════════
# REJECTION_BASE_PENALTY: Base risk added per settlement rejection
# ═══════════════════════════════════════════════════════════════════════════
# Current: 1.5
#
# ANALYSIS: Failed negotiations should be costly.
#   - Old value (1.0) was too gentle - players could reject freely
#   - At 1.5, a full rejection cycle (3 rejections) adds 1.5+2.25+3.0 = 6.75 risk
#   - This can push a stable situation into crisis territory
#
# TUNING GUIDANCE:
#   - If settlement attempts feel risk-free: increase toward 2.0
#   - If players never attempt settlement: decrease toward 1.0
#   - Run: "settlement negotiation" simulation tracking rejection patterns
#
REJECTION_BASE_PENALTY = 1.5

# ═══════════════════════════════════════════════════════════════════════════
# REJECTION_ESCALATION: How much penalty increases per subsequent rejection
# ═══════════════════════════════════════════════════════════════════════════
# Current: 0.5 (50% increase per rejection)
#
# ANALYSIS: Escalating penalties create urgency to reach agreement.
#   - 1st rejection: base × 1.0 = 1.5 risk
#   - 2nd rejection: base × 1.5 = 2.25 risk
#   - 3rd rejection: base × 2.0 = 3.0 risk
#
# TUNING GUIDANCE:
#   - If players drag out negotiations: increase toward 0.75
#   - If negotiations feel too pressured: decrease toward 0.25
#
REJECTION_ESCALATION = 0.5
```

### C.5 Reserve Parameters (Add If Needed)

These parameters are NOT active by default. Add them only if simulation reveals specific problems.

**STREAK PROTECTION EXPLAINED**

The problem: Without any cap or protection, late-game defection can be extremely profitable:
```
Turn 14 defection: 40% of ~45 surplus = 18 VP from one action!
```

Streak protection models "relationship capital" - the longer you cooperate, the harder it is to exploit the accumulated trust. Think of it as institutional resistance to betrayal.

```
WITHOUT protection (default):
  Turn 3:  40% of ~5 surplus = 2 VP
  Turn 10: 40% of ~30 surplus = 12 VP
  Turn 14: 40% of ~45 surplus = 18 VP  ← Late defection wins!

WITH 50% protection enabled:
  Turn 3:  40% × 1.0 = 2 VP   (no protection, streak too short)
  Turn 10: 40% × 0.5 = 6 VP   (50% protected by streak)
  Turn 14: 40% × 0.5 = 9 VP   (max protection)
  → Mid-game becomes the "sweet spot" for defection
```

Only enable this if the "Exploitation Timing Analysis" simulation shows turn 12+ as optimal.

```python
# ═══════════════════════════════════════════════════════════════════════════
# STREAK_PROTECTION_RATE: (RESERVE - add if late defection dominates)
# ═══════════════════════════════════════════════════════════════════════════
# Default: 0.0 (disabled)
# Enable if: "Exploitation Timing Analysis" shows optimal defection is turn 12+
#
# Formula:
#   effective_rate = CAPTURE_RATE * (1.0 - STREAK_PROTECTION_RATE * streak / MAX_PROTECTED_STREAK)
#
# STREAK_PROTECTION_RATE = 0.0  # Disabled by default
# MAX_PROTECTED_STREAK = 10

# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE_DECAY_PER_TURN: (RESERVE - alternative to protection)
# ═══════════════════════════════════════════════════════════════════════════
# Alternative mechanic: capture rate decays over game time regardless of streak
# Default: 0.0 (disabled)
#
# effective_rate = max(0.1, CAPTURE_RATE - CAPTURE_DECAY_PER_TURN * turn)
#
# Example at 0.02 decay:
#   Turn 1: 40%, Turn 10: 20%, Turn 15: 10% (floor)
#
# CAPTURE_DECAY_PER_TURN = 0.0  # Disabled
```

### C.6 Required Simulations for Parameter Tuning

Run these simulations when adjusting parameters:

**1. Exploitation Timing Analysis**
```
Purpose: Find the "optimal defection turn" for each parameter set
Method: Run 1000 games where Player A defects exactly once at turn N
Vary: N from 1 to 14
Measure: Total VP captured by Player A
Target: Peak should be mid-game (turns 5-9), not late-game
Action: If peak is turn 12+, enable STREAK_PROTECTION from C.5
```

**2. Rejection Penalty Impact**
```
Purpose: Tune settlement negotiation tension
Method: Run games with settlement-capable opponents
Vary: REJECTION_BASE_PENALTY at 1.0, 1.5, 2.0
Measure: Average rejections per settlement attempt, settlement success rate
Target: 1-2 average rejections, 40-60% success rate
```

**3. Full Balance Validation**
```
Purpose: Verify no dominant strategy exists
Method: Run all 21 opponent pairings, 100+ games each
Measure:
  - Total Value (VP_A + VP_B) - should average 100-130
  - VP Share - no strategy should achieve >120 total AND >55% share
  - Settlement rate - should be 30-70%
  - Mutual destruction rate - MUST be < 20% (target 10-18%)
  - Average game length - should be 10-16 turns
```

**4. Parameter Sweep Grid Search**
```
Purpose: Find optimal parameter combinations
Method: Grid search over key parameters
Parameters to sweep:
  - CAPTURE_RATE: [0.3, 0.4, 0.5]
  - REJECTION_BASE_PENALTY: [1.0, 1.5, 2.0]
  - DD_RISK_INCREASE: [0.8, 1.0, 1.2]  # Reduced range for higher settlement rates
Measure: All balance metrics from simulation #3
Target: Find parameter set that best meets all criteria
```
