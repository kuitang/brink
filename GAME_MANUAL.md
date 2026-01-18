# Brinksmanship: A Game-Theoretic Strategy Simulation

## Authoritative Game Manual v1.0

---

## Foundational Principles

This game is built on five inviolable design principles that govern all mechanics:

1. **Pure Game-Theoretic Matrices**: Every strategic interaction is resolved through a classic 2×2 (or sequential) game theory matrix. Players face genuine strategic dilemmas with no hidden "correct" answers.

2. **Information as a Game**: Intelligence gathering is not an action with guaranteed results—it is itself a game with strategic uncertainty. Reconnaissance can be detected; detection is escalation.

3. **No Hand of God Punishment**: There are no asymmetric penalties that punish one player while sparing another for symmetric actions. All variance and outcome modifications affect both players equally based on shared game state.

4. **Symmetric Mechanisms**: If an action destabilizes the situation, BOTH players face increased uncertainty. There is no mechanism by which defection harms only the defector.

5. **Uncertain Endpoints**: The game has no known final turn. Backward induction cannot operate because any turn might be the last. This emerges from probabilistic crisis termination, not arbitrary rules.

---

## Part I: Theoretical Foundations

### 1.1 Core Game Theory Literature

The game draws on foundational work in strategic interaction:

**John von Neumann & Oskar Morgenstern (1944)**: *Theory of Games and Economic Behavior* established the mathematical framework for strategic decision-making, including the minimax theorem for zero-sum games.

**John Nash (1950)**: "Equilibrium Points in N-Person Games" (*Proceedings of the National Academy of Sciences*) introduced the Nash Equilibrium—a strategy profile where no player can unilaterally improve their outcome. This concept underlies all matrix game analysis in this simulation.

**Anatol Rapoport & Melvin Guyer (1966)**: "A Taxonomy of 2×2 Games" (*General Systems*) systematically classified all 78 ordinally distinct 2×2 games, identifying the strategically interesting subset we employ.

**Robert Axelrod (1984)**: *The Evolution of Cooperation* demonstrated through computer tournaments that simple, retaliatory, forgiving strategies (particularly Tit-for-Tat) outperform complex strategies in iterated Prisoner's Dilemma. Key findings:
- Nice strategies (never defect first) outperform nasty ones
- The "shadow of the future" enables cooperation
- Clarity beats cleverness

**David Kreps, Paul Milgrom, John Roberts, & Robert Wilson (1982)**: "Rational Cooperation in the Finitely Repeated Prisoners' Dilemma" (*Journal of Economic Theory*) proved that even small uncertainty about opponent type can sustain cooperation in finite games—the theoretical foundation for our type-uncertainty mechanics.

### 1.2 Strategic Studies and International Relations

**Thomas Schelling (1960, 1966)**: *The Strategy of Conflict* and *Arms and Influence* provide the conceptual vocabulary for strategic interaction:

- **Focal Points (Schelling Points)**: When coordination is needed without communication, actors gravitate toward "obvious" solutions. Deviating from focal points signals something.

- **The Paradox of Commitment**: Binding yourself increases power. "Burning bridges" makes threats credible.

- **The Threat That Leaves Something to Chance**: Effective threats don't guarantee destruction—they increase the *probability* of losing control. Escalation is about risk manipulation.

- **Tacit Bargaining**: Adversaries can coordinate without explicit communication through shared expectations.

**Herman Kahn (1960, 1965)**: *On Thermonuclear War* and *On Escalation* introduced the escalation ladder concept—44 rungs from "ostensible crisis" to "spasm war." Key insight: escalation proceeds through recognizable thresholds, not continuously.

**Robert Jervis (1976, 1978)**: *Perception and Misperception in International Politics* and "Cooperation Under the Security Dilemma" (*World Politics*) identified the tragic dilemma at the heart of strategic interaction:

- **The Spiral Model**: Conflict arises from mutual fear and misperception. Neither side wants war, but defensive actions appear offensive. Prescription: reassure.

- **The Deterrence Model**: Conflict arises from aggression. Some actors genuinely seek expansion; weakness invites predation. Prescription: deter.

- **The Tragedy**: You cannot know which model applies to your specific opponent, and the prescriptions are opposite.

**John Mearsheimer (2001)**: *The Tragedy of Great Power Politics* argues that states cannot know others' intentions with certainty, so they must assume the worst (offensive realism). Implications:
- Relative gains matter more than absolute gains
- Today's partner is tomorrow's threat
- Cooperation is structurally fragile

**Kenneth Waltz (1979)**: *Theory of International Politics* establishes structural realism—system structure (anarchy, capability distribution) determines behavior more than unit-level factors.

### 1.3 Classical Strategic Thought

**Niccolò Machiavelli (1513, 1517)**: *The Prince* and *Discourses on Livy*:

- **Virtù vs. Fortuna**: Success requires both skill and luck. Fortune is like a river—you can't stop floods, but you can build embankments.

- **The Lion and the Fox**: "A prince must be a fox to recognize traps, and a lion to frighten wolves."

- **Economy of Violence**: "Injuries should be done all together, so that being less tasted, they will give less offense."

**Carl von Clausewitz (1832)**: *On War*:

- **War as Politics**: Military action serves political objectives, not the reverse.
- **Fog of War**: Information is always incomplete and distorted.
- **Friction**: Everything in war is simple, but simple things are difficult.
- **Culminating Point**: Every offensive reaches a point where it can advance no further.

### 1.4 Repeated Game Theory

**The Folk Theorem**: In infinitely repeated games with sufficiently patient players, *any* payoff giving both players more than their one-shot Nash equilibrium can be sustained as equilibrium.

**The Backward Induction Problem**: In finitely repeated games with known endpoint:
- Round N: No future, defect dominates
- Round N-1: Both know Round N will be mutual defection, defect dominates
- This unravels to Round 1

**The Resolution**: Uncertain endpoints prevent backward induction. If you don't know which turn is last, you cannot reason backward from it.

---

## Part II: The 24 Strategic Game Types

The game employs distinct matrix structures, each capturing a different strategic dilemma:

### Category A: Dominant Strategy Games

**1. Prisoner's Dilemma**
|  | Cooperate | Defect |
|--|-----------|--------|
| **Cooperate** | 3, 3 | 1, 4 |
| **Defect** | 4, 1 | 2, 2 |

*Tension*: Individual rationality leads to collective irrationality. Nash equilibrium (D,D) is Pareto-inferior to (C,C).

*Scenarios*: Arms races, trade agreements, environmental accords, corporate price-fixing

**2. Deadlock**
|  | Cooperate | Defect |
|--|-----------|--------|
| **Cooperate** | 2, 2 | 1, 4 |
| **Defect** | 4, 1 | 3, 3 |

*Tension*: Both prefer mutual defection. No cooperative solution exists.

*Scenarios*: Existential ideological conflicts, zero-sum territorial disputes

**3. Harmony**
|  | Cooperate | Defect |
|--|-----------|--------|
| **Cooperate** | 4, 4 | 3, 2 |
| **Defect** | 2, 3 | 1, 1 |

*Tension*: None—cooperation dominates. Establishes baseline for why conflict is a choice.

*Scenarios*: Mutually beneficial trade, obvious coordination

### Category B: Anti-Coordination Games

**4. Chicken (Hawk-Dove)**
|  | Dove | Hawk |
|--|------|------|
| **Dove** | 3, 3 | 2, 4 |
| **Hawk** | 4, 2 | 1, 1 |

*Tension*: Two pure equilibria (Dove-Hawk, Hawk-Dove) plus mixed. Commitment and credibility are paramount.

*Scenarios*: Cuban Missile Crisis, territorial standoffs, hostile takeovers, government shutdowns

**5. Volunteer's Dilemma**
|  | Volunteer | Abstain |
|--|-----------|---------|
| **Volunteer** | 2, 2 | 2, 3 |
| **Abstain** | 3, 2 | 0, 0 |

*Tension*: Someone must sacrifice, but everyone hopes someone else will.

*Scenarios*: Crisis intervention, public goods provision, whistleblowing

**6. War of Attrition**
Continuous-time game: both pay costs each period; first to quit loses.

*Tension*: Rational to quit immediately OR commit fully—nothing in between.

*Scenarios*: Sieges, price wars, labor strikes, litigation

### Category C: Coordination Games

**7. Pure Coordination**
|  | A | B |
|--|---|---|
| **A** | 2, 2 | 0, 0 |
| **B** | 0, 0 | 2, 2 |

*Tension*: Two equilibria, players indifferent. Schelling focal points determine outcome.

*Scenarios*: Standard-setting, communication protocols, meeting points

**8. Stag Hunt (Assurance Game)**
|  | Stag | Hare |
|--|------|------|
| **Stag** | 4, 4 | 0, 3 |
| **Hare** | 3, 0 | 2, 2 |

*Tension*: (Stag, Stag) is payoff-dominant; (Hare, Hare) is risk-dominant. Problem is trust, not incentives.

*Scenarios*: Alliance formation, joint ventures, revolution coordination

**9. Battle of the Sexes**
|  | Opera | Football |
|--|-------|----------|
| **Opera** | 3, 2 | 0, 0 |
| **Football** | 0, 0 | 2, 3 |

*Tension*: Coordination with distributional conflict. Who leads?

*Scenarios*: Standard-setting with competitive advantage, protocol disputes, merger negotiations

**10. Leader (Asymmetric Coordination)**
|  | Follow | Lead |
|--|--------|------|
| **Follow** | 0, 0 | 3, 4 |
| **Lead** | 4, 3 | 1, 1 |

*Tension*: One should lead, one follow—but if both lead, conflict.

*Scenarios*: Hierarchy establishment, initiative-taking, first-mover situations

### Category D: Zero-Sum and Information Games

**11. Matching Pennies**
|  | Heads | Tails |
|--|-------|-------|
| **Heads** | +1, −1 | −1, +1 |
| **Tails** | −1, +1 | +1, −1 |

*Tension*: Pure conflict. Only mixed-strategy equilibrium exists.

*Scenarios*: Tactical deception, reconnaissance vs. counterintelligence

**12. Inspection Game**
|  | Comply | Cheat |
|--|--------|-------|
| **Inspect** | −c, 0 | B−c, −P |
| **Trust** | 0, 0 | −L, G |

*Tension*: Inspector wants to catch cheaters; cheater wants to avoid detection. Mixed equilibrium.

*Scenarios*: Arms verification, compliance monitoring, auditing

**13. Reconnaissance Game** (Custom variant for this simulation)
|  | Vigilant | Project |
|--|----------|---------|
| **Probe** | Detected (Risk+1, no info) | Success (learn opponent Position) |
| **Mask** | Stalemate | Exposed (receive disinformation) |

*Tension*: Information gathering IS escalation. Pure game theory, no "spend resource, gain intel."

### Category E: Sequential Games

**14. Trust Game (Investment Game)**
Sequential: A gives x to B; B receives 3x; B returns y to A.

*Tension*: Backward induction says B returns nothing, so A gives nothing. But cooperation is profitable.

*Scenarios*: Initial relationship building, investment decisions

**15. Ultimatum Game**
Sequential: A proposes split; B accepts or rejects (both get nothing on rejection).

*Tension*: Backward induction says A offers minimum, B accepts. Real humans reject "unfair" offers.

*Scenarios*: Settlement negotiations, take-it-or-leave-it demands

**16. Centipede Game**
Sequential, multiple rounds: each player can "take" (end game) or "pass" (double pot, give opponent next move).

*Tension*: Backward induction says take immediately. But mutual passing is profitable.

*Scenarios*: Escalating cooperation, trust-building over time

**17. Entry Deterrence**
Sequential: Entrant chooses enter/stay out; Incumbent chooses fight/accommodate.

*Tension*: If entry occurs, incumbent prefers accommodating. But incumbent wants to *threaten* fighting.

*Scenarios*: Market entry, territorial expansion, sphere of influence

**18. Chain Store Paradox**
Repeated entry deterrence across multiple markets.

*Tension*: Fight early to deter later entrants? Reputation effects complicate backward induction.

*Scenarios*: Serial confrontations, reputation establishment

### Category F: Signaling Games

**19. Beer-Quiche (Signaling)**
- Sender has private type (Strong or Weak)
- Sender chooses signal (Beer or Quiche)
- Receiver observes signal, chooses Fight or Defer
- Strong types prefer Beer, Weak prefer Quiche

*Tension*: Multiple equilibria (separating, pooling). Can signals credibly reveal type?

*Scenarios*: Military posturing, corporate bluffing, diplomatic signals

**20. Cheap Talk**
- Sender knows state of world
- Sender sends costless message
- Receiver acts

*Tension*: Cheap talk conveys information only if interests are partially aligned. Pure conflict = meaningless talk.

*Scenarios*: Diplomatic communications, corporate announcements

**21. Costly Signaling (Spence)**
- Sender has private type (High or Low quality)
- Sender can pay cost to signal
- Cost is lower for High types

*Tension*: In equilibrium, only High types signal. Cost creates credibility.

*Scenarios*: Military mobilization, economic sanctions, public commitments

### Category G: Specialized Games

**22. Dollar Auction**
Sequential bidding: highest bidder wins, but BOTH bidders pay their bids.

*Tension*: Escalation trap. Once invested, sunk costs drive continued bidding.

*Scenarios*: Arms races, bidding wars, honor contests

**23. Traveler's Dilemma**
Both name a number 2-100; lower number wins, plus bonus. Higher number gets lower number minus penalty.

*Tension*: Nash equilibrium is minimum, but most real players choose high numbers.

*Scenarios*: Testing common knowledge of rationality

**24. Security Dilemma (Custom formulation)**
|  | Arm | Disarm |
|--|-----|--------|
| **Arm** | 2, 2 | 4, 1 |
| **Disarm** | 1, 4 | 3, 3 |

*Tension*: Structurally a Prisoner's Dilemma, but the interpretation matters—defensive arming appears offensive.

*Scenarios*: Arms buildups, security competition

---

## Part III: Game State and Mechanics

### 3.1 State Variables

| Variable | Type | Range | Initial | Description |
|----------|------|-------|---------|-------------|
| Position_A | Per player | 0–10 | 5 | Player A's relative power/advantage |
| Position_B | Per player | 0–10 | 5 | Player B's relative power/advantage |
| Resources_A | Per player | 0–10 | 5 | Player A's reserves (political capital, treasury) |
| Resources_B | Per player | 0–10 | 5 | Player B's reserves |
| Cooperation_Score | **Shared** | 0–10 | 5 | Overall relationship trajectory |
| Stability | **Shared** | 1–10 | 5 | Predictability of both players' behavior |
| Risk_Level | **Shared** | 0–10 | 2 | Position on escalation ladder |
| Turn | Shared | 1–N | 1 | Current turn (N is uncertain, range 10–18) |
| Previous_Type_A | Per player | C/D | None | Player A's last action classification |
| Previous_Type_B | Per player | C/D | None | Player B's last action classification |

### 3.2 Action Classification

Every action is classified as one of two types:

| **Cooperative (C)** | **Competitive (D)** |
|---------------------|---------------------|
| De-escalate | Escalate |
| Hold / Maintain | Aggressive Pressure |
| Propose Settlement | Issue Ultimatum |
| Back Channel | Show of Force |
| Concede | Demand |
| Withdraw | Advance |

### 3.3 Turn Structure

```
TURN SEQUENCE

1. BRIEFING
   - Narrative situation presented (from pre-generated scenario)
   - Current shared state displayed (Risk Level, Cooperation Score, Stability)
   - Noisy intelligence on opponent's Position and Resources (±2)
   - Your own Position and Resources (exact)

2. DECISION (Simultaneous)
   - Each player chooses from action menu (4-6 options depending on Risk Level)
   - Actions are classified as Cooperative (C) or Competitive (D)
   - Settlement proposal is a special action

3. RESOLUTION
   - If both proposed settlement: compare offers, negotiate
   - If one proposed settlement: other player accepts or rejects
   - Otherwise: resolve using hidden matrix game
     → Position changes based on matrix payoffs
     → Resource costs deducted
     → Risk Level changes based on escalation dynamics

4. STATE UPDATE
   - Update Cooperation Score:
     * CC (both cooperative): +1
     * DD (both competitive): −1
     * CD or DC (mixed): no change
   - Update Stability:
     * 0 switches (both consistent): Stability = min(10, Stability + 1)
     * 1 switch: Stability = max(1, Stability ÷ 2)
     * 2 switches: Stability = max(1, (Stability ÷ 2) − 1)
   - Update Previous_Type for each player

5. CHECK DETERMINISTIC ENDINGS
   - If Risk = 10: Mutual Destruction → END
   - If either Position = 0: That player loses → END
   - If either Resources = 0: That player loses → END

6. CHECK CRISIS TERMINATION (Turn ≥ 9 only)
   - If Risk > 6: Roll for Crisis Termination
   - P(Termination) = (Risk − 6) × 0.10
   - If triggered: Final Resolution → END

7. CHECK NATURAL ENDING
   - If Turn = Max_Turn (unknown to players, 10-18): Final Resolution → END

8. ADVANCE
   - Turn++
   - Return to Step 1
```

### 3.4 Information and Intelligence

**What You Always Know (Perfect Information)**:
- Your own Position (exact)
- Your own Resources (exact)
- Current Risk Level
- Current Cooperation Score
- Current Stability
- Turn number
- History of your own actions
- History of observable outcomes

**What You Never Know Directly**:
- Opponent's exact Position
- Opponent's exact Resources
- Opponent's "type" (if playing vs. LLM)
- Exact payoff values in current matrix
- How many turns remain

**Noisy Intelligence**:
```
Observed_Opponent_Position = True_Position + Uniform(−2, +2)
Observed_Opponent_Resources = True_Resources + Uniform(−2, +2)
```

**Information Games** (played as matrix games, not actions):
- **Reconnaissance Game**: Probe vs. Mask against Vigilant vs. Project
- **Signaling Games**: Costly signals that reveal or conceal type
- **Cheap Talk**: Communication that may or may not be credible

---

## Part IV: Variance and Final Resolution

### 4.1 The Symmetric Variance Principle

**Variance is a property of the SITUATION, not the individual.**

When either player acts unpredictably, the entire situation becomes chaotic—BOTH players face increased uncertainty. There is no mechanism by which defection increases variance "only for the defector."

This captures reality: if your opponent suddenly betrays you, YOU face uncertainty too. What are they planning? How should you respond? The fog of war thickens for everyone.

### 4.2 Variance Calculation Formula

```
Shared_σ = Base_σ × Chaos_Factor × Instability_Factor × Act_Multiplier
```

**Base_σ** (from Risk Level):
```
Base_σ = 10 + (Risk_Level × 2)
```

| Risk Level | Base_σ |
|------------|--------|
| 0 | 10 |
| 5 | 20 |
| 10 | 30 |

**Chaos_Factor** (from Cooperation Score):
```
Chaos_Factor = 1.5 − (Cooperation_Score / 20)
```

| Cooperation Score | Chaos Factor |
|-------------------|--------------|
| 10 (strong cooperation) | 1.00 |
| 5 (neutral) | 1.25 |
| 0 (hostile) | 1.50 |

**Instability_Factor** (from shared Stability):
```
Instability_Factor = 1 + (10 − Stability)² / 50
```

| Stability | Instability Factor |
|-----------|-------------------|
| 10 (very consistent) | 1.00 |
| 7 | 1.18 |
| 5 | 1.50 |
| 3 | 1.98 |
| 1 (just switched) | 2.62 |

**Act_Multiplier** (from turn number):

| Act | Turns | Multiplier |
|-----|-------|------------|
| I (Setup) | 1–4 | 0.5 |
| II (Confrontation) | 5–8 | 1.0 |
| III (Resolution) | 9+ | 1.5 |

### 4.3 Final Resolution Calculation

```python
def final_resolution(state):
    # Expected values from position
    total_pos = state.position_a + state.position_b
    if total_pos == 0:
        ev_a = 50
    else:
        ev_a = (state.position_a / total_pos) * 100
    ev_b = 100 - ev_a
    
    # Calculate shared variance
    base_sigma = 10 + (state.risk_level * 2)
    chaos_factor = 1.5 - (state.cooperation_score / 20)
    instability_factor = 1 + ((10 - state.stability) ** 2) / 50
    act_multiplier = 1.5  # Act III
    
    shared_sigma = base_sigma * chaos_factor * instability_factor * act_multiplier
    
    # Single random draw affects both symmetrically
    noise = random.gauss(0, shared_sigma)
    
    vp_a = clamp(ev_a + noise, 5, 95)
    vp_b = 100 - vp_a
    
    return vp_a, vp_b
```

### 4.4 Settlement Terms

Available after Turn 4 unless Stability ≤ 2.

```
Position_Difference = Your_Position − Opponent_Position
Cooperation_Bonus = (Cooperation_Score − 5) × 2

Your_Suggested_VP = 50 + (Position_Difference × 5) + Cooperation_Bonus

Constraints:
  Your_Min_Offer = max(20, Your_Suggested_VP - 10)
  Your_Max_Offer = min(80, Your_Suggested_VP + 10)
```

Settlement requires opponent acceptance. Rejected settlements increase Risk by 1.

### 4.5 Deterministic Endings

| Trigger | Result |
|---------|--------|
| Risk = 10 | Mutual Destruction: both receive 20 VP |
| Position = 0 | That player loses: 10 VP. Opponent: 90 VP |
| Resources = 0 | That player loses: 15 VP. Opponent: 85 VP |

### 4.6 Crisis Termination (Probabilistic)

Starting Turn 9, at the END of each turn:

```
if Risk_Level > 6:
    P(Crisis_Termination) = (Risk_Level - 6) × 0.10
    if random() < P(Crisis_Termination):
        trigger Final_Resolution
```

| Risk Level | P(Termination per Turn) |
|------------|------------------------|
| 7 | 10% |
| 8 | 20% |
| 9 | 30% |
| 10 | 100% (automatic) |

**Why This Eliminates Backward Induction**:

At Risk 8, Turn 10:
- P(reaching Turn 11) = 80%
- P(reaching Turn 12) = 64%
- P(reaching Turn 13) = 51%

Players cannot plan "defect on last turn" because they don't know which turn is last.

---

## Part V: Stability Update Rules

### 5.1 Definition of "Switch"

A player "switches" if their action type this turn differs from their action type last turn.

- Turn 1: No previous action, no switch possible
- Turn 2+: Compare current action type (C or D) to previous action type

### 5.2 Stability Update

**At the end of each turn, count switches:**

| Switches | Update Rule |
|----------|-------------|
| 0 (both consistent) | Stability = min(10, Stability + 1) |
| 1 (one switched) | Stability = max(1, Stability ÷ 2) |
| 2 (both switched) | Stability = max(1, (Stability ÷ 2) − 1) |

### 5.3 Why This Discourages "Cooperate Then Defect"

**Trajectory: Consistent Cooperator**

| Turn | Action | Stability |
|------|--------|-----------|
| 1 | C | 5 |
| 2 | C | 6 |
| 3 | C | 7 |
| ... | C | ... |
| 10 | C | 10 |
| 11 | C | 10 |
| Final Resolution | — | Instability Factor = 1.0 |

**Trajectory: Cooperator Who Defects at End**

| Turn | Action | Stability |
|------|--------|-----------|
| 1–10 | C | → 10 |
| 11 | **D** (switch!) | → 5 |
| Final Resolution | — | Instability Factor = 1.5 |

The late defector creates 50% more variance for BOTH players. Combined with Cooperation Score changes, total variance increase is substantial.

**The Key Property**: Consistency is rewarded regardless of what you're consistent about. A consistent defector has the same low variance as a consistent cooperator.

---

## Part VI: Scenario Structure

### 6.1 Three-Act Structure

| Act | Turns | Stakes | Typical Games | Narrative Function |
|-----|-------|--------|---------------|-------------------|
| I (Setup) | 1–4 | Low (0.5× payoffs) | Coordination, Stag Hunt, early PD | Establish positions, learn opponent |
| II (Confrontation) | 5–8 | Standard (1.0×) | Chicken, Inspection, Signaling | Direct conflict, testing |
| III (Resolution) | 9–end | High (1.5×) | War of Attrition, Ultimatum, high-stakes Chicken | Endgame, settlement attempts |

### 6.2 Pre-Generated Scenarios

Scenarios are generated by LLM before gameplay and validated for balance. Each scenario includes:

1. **Setting**: Theme, time period, stakes
2. **Arc structure**: Which turns are escalation points vs. breathing room
3. **Branch conditions**: How outcomes determine narrative paths
4. **Matrix assignments**: Which game theory structure applies each turn
5. **Narrative snippets**: Briefings and outcome descriptions
6. **Uncertain length**: Total turns is 10–18, unknown to players

### 6.3 Scenario Themes

The game supports multiple thematic settings:

- **Ancient History**: Succession crises, alliance formation, territorial disputes
- **Palace Intrigue**: Court politics, succession, factional conflict
- **Cold War**: Superpower brinkmanship, proxy conflicts, arms control
- **Contemporary Geopolitics**: Trade wars, territorial disputes, alliance politics
- **Corporate Governance**: Hostile takeovers, board conflicts, merger negotiations
- **Legal Strategy**: Settlement negotiations, litigation tactics

---

## Part VII: Reference Tables

### 7.1 Variance Multipliers

| Stability | (10 − Stability)² | Instability Factor |
|-----------|-------------------|-------------------|
| 10 | 0 | 1.00 |
| 9 | 1 | 1.02 |
| 8 | 4 | 1.08 |
| 7 | 9 | 1.18 |
| 6 | 16 | 1.32 |
| 5 | 25 | 1.50 |
| 4 | 36 | 1.72 |
| 3 | 49 | 1.98 |
| 2 | 64 | 2.28 |
| 1 | 81 | 2.62 |

### 7.2 Cooperation Score Effects

| Score | Chaos Factor | Settlement Bonus |
|-------|--------------|------------------|
| 10 | 1.00 | +10 VP floor for both |
| 8 | 1.10 | +6 |
| 6 | 1.20 | +2 |
| 5 | 1.25 | 0 |
| 4 | 1.30 | −2 |
| 2 | 1.40 | −6 |
| 0 | 1.50 | −10 |

### 7.3 Crisis Termination Probabilities

| Risk Level | P(Termination/Turn) | P(Reaching Turn 12 from Turn 9) |
|------------|--------------------|---------------------------------|
| 6 or below | 0% | 100% |
| 7 | 10% | 73% |
| 8 | 20% | 51% |
| 9 | 30% | 34% |

### 7.4 Example Variance Scenarios

| Scenario | Risk | Coop Score | Stability | Act | Shared_σ |
|----------|------|------------|-----------|-----|----------|
| Peaceful early game | 3 | 7 | 8 | I | ~8 |
| Neutral mid-game | 5 | 5 | 5 | II | ~25 |
| Tense late game | 7 | 3 | 6 | III | ~48 |
| Chaotic crisis | 9 | 1 | 2 | III | ~95 |

---

## Part VIII: Player-Facing Rules

### How the Game Works

You and your opponent face a series of strategic dilemmas over 10–18 turns. Each turn, you choose from a menu of actions. Your choices and your opponent's choices are resolved using game theory—the outcome depends on what BOTH of you do.

Your goal: Maximize your Victory Points (VP). VP are determined at game end by your Position relative to your opponent, modified by variance.

### The State Variables

**Your Position (0–10)**: Your relative power and advantage. Higher is better. If it reaches 0, you lose.

**Your Resources (0–10)**: Your reserves—political capital, treasury, military reserves. Some actions cost Resources. If it reaches 0, you lose.

**Risk Level (shared, 0–10)**: How dangerous the situation is. Higher Risk means higher stakes and higher chance of sudden crisis termination. If it reaches 10, both players suffer Mutual Destruction.

**Cooperation Score (shared, 0–10)**: The overall relationship trajectory. Mutual cooperation increases it; mutual competition decreases it. Higher scores mean lower variance and better settlement terms.

**Stability (shared, 1–10)**: How predictable both players have been. Consistent behavior increases Stability; switching behavior crashes it. Higher Stability means lower variance.

### The Stability System

Each action is either *Cooperative* (de-escalate, hold, propose settlement) or *Competitive* (escalate, demand, pressure).

- If you take the same type of action as last turn: You're consistent
- If you switch types: You've become unpredictable

**Stability Update**:
- Both players consistent: Stability +1
- One player switches: Stability drops sharply (halved)
- Both players switch: Stability drops severely (halved minus 1)

**Why it matters**: When the game ends, your outcome depends on your Position AND on variance. Higher Stability = lower variance = more predictable outcomes.

### How the Game Ends

**Settlement (you control this)**:
After Turn 4, either player can propose a settlement. If both agree on terms, the game ends with certain VP. This is the only way to guarantee your outcome.

**Crisis Termination (partially controlled)**:
Starting Turn 9, if Risk > 6, there's a chance each turn that the situation spirals out of control:
- Risk 7: 10% per turn
- Risk 8: 20% per turn
- Risk 9: 30% per turn
- Risk 10: Automatic Mutual Destruction

**Elimination**:
If your Position or Resources hit 0, you lose immediately.

**Natural End**:
The game has a maximum length between 10 and 18 turns. You don't know exactly when.

### Strategic Implications

**If you're ahead**: Stability is your friend. Keep things predictable. Propose settlement to lock in your advantage. Don't give your opponent the chaos they need.

**If you're behind**: Chaos might be your hope. High variance creates upset potential. But destabilizing the situation helps your opponent's variance too—you're creating a coin flip, not a sure thing.

**The key insight**: Variance is symmetric. If you destabilize things, BOTH players face more uncertainty. The question is whether your Position advantage or the variance dominates.

**You cannot plan "defect on the last turn"** because you don't know which turn is last. Every turn from Turn 9 onward might end the game. Plan accordingly.

### Action Types Reference

| Cooperative Actions | Competitive Actions |
|---------------------|---------------------|
| De-escalate | Escalate |
| Hold Position | Aggressive Pressure |
| Propose Settlement | Issue Ultimatum |
| Back Channel | Show of Force |
| Concede | Demand |

---

## Appendix: Bibliography

Axelrod, Robert. *The Evolution of Cooperation*. Basic Books, 1984.

Clausewitz, Carl von. *On War*. Translated by Michael Howard and Peter Paret. Princeton University Press, 1832/1976.

Jervis, Robert. *Perception and Misperception in International Politics*. Princeton University Press, 1976.

Jervis, Robert. "Cooperation Under the Security Dilemma." *World Politics* 30, no. 2 (1978): 167–214.

Kahn, Herman. *On Thermonuclear War*. Princeton University Press, 1960.

Kahn, Herman. *On Escalation: Metaphors and Scenarios*. Praeger, 1965.

Kreps, David, Paul Milgrom, John Roberts, and Robert Wilson. "Rational Cooperation in the Finitely Repeated Prisoners' Dilemma." *Journal of Economic Theory* 27 (1982): 245–252.

Machiavelli, Niccolò. *The Prince*. 1513.

Machiavelli, Niccolò. *Discourses on Livy*. 1517.

Mearsheimer, John J. *The Tragedy of Great Power Politics*. W.W. Norton, 2001.

Nash, John. "Equilibrium Points in N-Person Games." *Proceedings of the National Academy of Sciences* 36 (1950): 48–49.

Rapoport, Anatol, and Melvin Guyer. "A Taxonomy of 2×2 Games." *General Systems* 11 (1966): 203–214.

Schelling, Thomas C. *The Strategy of Conflict*. Harvard University Press, 1960.

Schelling, Thomas C. *Arms and Influence*. Yale University Press, 1966.

von Neumann, John, and Oskar Morgenstern. *Theory of Games and Economic Behavior*. Princeton University Press, 1944.

Waltz, Kenneth N. *Theory of International Politics*. Addison-Wesley, 1979.

---

*Document Version: 1.0*
*Last Updated: January 2026*
