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
| Turn | Shared | 1–N | 1 | Current turn (N is uncertain, range 12–16) |
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
   - Your Intelligence on opponent (see Section 3.4 - uncertainty-bounded estimate)
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

6. CHECK CRISIS TERMINATION (Turn ≥ 10 only)
   - If Risk > 7: Roll for Crisis Termination
   - P(Termination) = (Risk − 7) × 0.08
   - If triggered: Final Resolution → END

7. CHECK NATURAL ENDING
   - If Turn = Max_Turn (unknown to players, 12-16): Final Resolution → END

8. ADVANCE
   - Turn++
   - Return to Step 1
```

### 3.4 Information and Intelligence

**Core Principle**: You never passively observe opponent state. Information is a strategic resource acquired through information games, and it decays over time.

**What You Always Know (Perfect Information)**:
- Your own Position (exact)
- Your own Resources (exact)
- Current Risk Level
- Current Cooperation Score
- Current Stability
- Turn number
- History of your own actions
- History of observable outcomes (your own state changes)

**What You Never Know Directly**:
- Opponent's exact Position (must acquire through information games)
- Opponent's exact Resources (must acquire through information games)
- Opponent's "type" (if playing vs. LLM)
- Exact payoff values in current matrix
- How many turns remain

**Information State Model**:

Each player maintains an `InformationState` about their opponent:

```
InformationState:
  position_bounds: [0.0, 10.0]     # Hard bounds, always valid
  resources_bounds: [0.0, 10.0]    # Hard bounds, always valid
  known_position: Optional[float]  # From last successful recon
  known_position_turn: Optional[int]
  known_resources: Optional[float] # From last successful inspection
  known_resources_turn: Optional[int]
```

**Information Decay**:

Information becomes stale as opponent's state changes each turn:
```
uncertainty = min(turns_since_known × 0.8, 5.0)
estimate_range = [known_value - uncertainty, known_value + uncertainty]
```

After ~6 turns, information is nearly useless (uncertainty = 5.0, which is half the scale).

**Information Acquisition Methods**:

1. **Reconnaissance Game** (learn opponent's Position)
2. **Inspection Game** (learn opponent's Resources)
3. **Costly Signaling** (reveal bounds on your own Position)
4. **Inference from Outcomes** (learn opponent's action, not state)
5. **Inference from Settlement Proposals** (cheap talk, may be unreliable)

See Section 3.6 for detailed information game mechanics.

### 3.5 State Deltas (How Outcomes Affect State)

Each turn's matrix outcome produces **State Deltas**—changes to Position, Resources, and Risk:

| Delta Type | Range | Description |
|------------|-------|-------------|
| Position (each player) | -1.5 to +1.5 | Relative advantage change |
| Resource Cost (each) | 0 to 1.0 | Resources expended |
| Risk | -1.0 to +2.0 | Shared escalation level |

**Act Scaling**: Deltas are multiplied by act factor:
- Act I (turns 1-4): ×0.7
- Act II (turns 5-8): ×1.0
- Act III (turns 9+): ×1.3

**Example State Deltas for Prisoner's Dilemma**:

| Outcome | Pos_A | Pos_B | Res Cost | Risk |
|---------|-------|-------|----------|------|
| CC (mutual cooperation) | +0.5 | +0.5 | 0 | -0.5 |
| CD (A exploited) | -1.0 | +1.0 | 0 | +0.5 |
| DC (B exploited) | +1.0 | -1.0 | 0 | +0.5 |
| DD (mutual defection) | -0.3 | -0.3 | 0.5 each | +1.0 |

**Example State Deltas for Chicken**:

| Outcome | Pos_A | Pos_B | Res Cost | Risk |
|---------|-------|-------|----------|------|
| Dove-Dove | +0.3 | +0.3 | 0 | -0.5 |
| Dove-Hawk | -0.5 | +1.0 | 0 | +0.5 |
| Hawk-Dove | +1.0 | -0.5 | 0 | +0.5 |
| Hawk-Hawk (crash) | -1.5 | -1.5 | 1.0 each | +2.0 |

**Balance Constraints**:
- Position changes are near-zero-sum: |Δpos_a + Δpos_b| ≤ 0.5
- Resources never increase from outcomes (only decrease or stay same)
- Mutual cooperation reduces Risk; mutual defection increases it

### 3.6 Information Game Mechanics

Information games allow players to acquire intelligence about their opponent's state. Playing an information game consumes your action for that turn—you cannot play both an information game AND a regular strategic game in the same turn.

#### 3.6.1 Reconnaissance Game (Position Intelligence)

**Purpose**: Learn opponent's exact Position.

**Initiation**: Either player may choose "Initiate Reconnaissance" as their action. If chosen, BOTH players enter the Reconnaissance game that turn instead of the regular strategic game.

**Cost**: The initiating player pays 0.5 Resources.

**Matrix Structure** (Matching Pennies variant):

|  | Opponent: Vigilant | Opponent: Project |
|--|-------------------|-------------------|
| **You: Probe** | Detected | Success |
| **You: Mask** | Stalemate | Exposed |

**Outcomes**:

| Outcome | Your Info Gain | Opponent Info Gain | Other Effects |
|---------|---------------|-------------------|---------------|
| Probe + Vigilant (Detected) | None | Learns you attempted recon | Risk +0.5 |
| Probe + Project (Success) | Learn opponent's exact Position | None | — |
| Mask + Vigilant (Stalemate) | None | None | — |
| Mask + Project (Exposed) | None | Learns your exact Position | — |

**Nash Equilibrium**: Mixed strategy (50% Probe, 50% Mask) for both players.

**Expected Value**:
- 25% chance you learn their Position
- 25% chance they learn your Position
- 12.5% chance of escalation (Risk +0.5)
- Cost: 0.5 Resources (initiator only)

#### 3.6.2 Inspection Game (Resource Intelligence)

**Purpose**: Learn opponent's exact Resources.

**Initiation**: Either player may choose "Initiate Inspection" as their action.

**Cost**: Initiating player pays 0.3 Resources.

**Matrix Structure**:

|  | Opponent: Comply | Opponent: Cheat |
|--|-----------------|-----------------|
| **You: Inspect** | Verified | Caught |
| **You: Trust** | Nothing | Exploited |

**Outcomes**:

| Outcome | Your Info Gain | Opponent Effect | Other Effects |
|---------|---------------|-----------------|---------------|
| Inspect + Comply (Verified) | Learn opponent's exact Resources | — | — |
| Inspect + Cheat (Caught) | Learn opponent's exact Resources | Opponent Risk +1, Position -0.5 | — |
| Trust + Comply (Nothing) | None | — | — |
| Trust + Cheat (Exploited) | None | Opponent Position +0.5 | — |

**Nash Equilibrium**: Mixed strategy; inspection probability depends on cost-benefit ratio.

#### 3.6.3 Costly Signaling (Voluntary Disclosure)

**Purpose**: Credibly reveal information about your own Position.

**Mechanism**: You may UNILATERALLY choose to signal alongside your regular action (no turn cost). You pay a resource cost that depends on your true Position:

| Your Position | Signal Cost |
|---------------|-------------|
| ≥ 7 (Strong) | 0.3 Resources |
| 4–6 (Medium) | 0.7 Resources |
| ≤ 3 (Weak) | 1.2 Resources |

**What Opponent Learns**:
- If you signal successfully: Opponent learns "Your Position ≥ 4"
- Bayesian inference: Given you signaled, P(Position ≥ 7) is elevated

**Design Insight**: Only strong players can profitably signal because the cost is prohibitive for weak players. This is the "burning money" mechanism from Spence signaling theory.

#### 3.6.4 Inference from Outcomes

After each turn, you observe your own state changes. You can infer opponent's likely ACTION (not state):

| Your Action | Your Position Change | Likely Opponent Action |
|-------------|---------------------|----------------------|
| Cooperate | -1.0 | Defect |
| Cooperate | +0.5 | Cooperate |
| Defect | +1.0 | Cooperate |
| Defect | -0.3, Resources -0.5 | Defect |

**Limitation**: This reveals what opponent DID, not what their Position/Resources ARE.

#### 3.6.5 Information Display

What players see each turn:

```
YOUR STATUS (exact)           INTELLIGENCE ON OPPONENT
Position: 6.0                 Position: UNKNOWN
Resources: 4.2                  Last recon: Turn 3, value was 5.2
                                Uncertainty: ±2.4 (4 turns stale)
                                Estimate: 2.8 – 7.6

                              Resources: UNKNOWN
                                No inspection data
                                Estimate: 0.0 – 10.0
```

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
Base_σ = 8 + (Risk_Level × 1.2)
```

| Risk Level | Base_σ |
|------------|--------|
| 0 | 8 |
| 5 | 14 |
| 10 | 20 |

**Chaos_Factor** (from Cooperation Score):
```
Chaos_Factor = 1.2 − (Cooperation_Score / 50)
```

| Cooperation Score | Chaos Factor |
|-------------------|--------------|
| 10 (strong cooperation) | 1.00 |
| 5 (neutral) | 1.10 |
| 0 (hostile) | 1.20 |

**Instability_Factor** (from shared Stability):
```
Instability_Factor = 1 + (10 − Stability) / 20
```

| Stability | Instability Factor |
|-----------|-------------------|
| 10 (very consistent) | 1.00 |
| 7 | 1.15 |
| 5 | 1.25 |
| 3 | 1.35 |
| 1 (just switched) | 1.45 |

**Act_Multiplier** (from turn number):

| Act | Turns | Multiplier |
|-----|-------|------------|
| I (Setup) | 1–4 | 0.7 |
| II (Confrontation) | 5–8 | 1.0 |
| III (Resolution) | 9+ | 1.3 |

Note: This is the same multiplier used for state deltas, ensuring consistency.

**Example Variance Values**:

| Scenario | Risk | Coop | Stab | Act | Shared_σ |
|----------|------|------|------|-----|----------|
| Peaceful early | 3 | 7 | 8 | I | ~10 |
| Neutral mid | 5 | 5 | 5 | II | ~19 |
| Tense late | 7 | 3 | 6 | III | ~27 |
| Chaotic crisis | 9 | 1 | 2 | III | ~37 |

This formula ensures variance stays in a playable range (σ ≈ 10-40) where position matters but outcomes aren't purely deterministic.

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

    # Calculate shared variance (revised formula)
    base_sigma = 8 + (state.risk_level * 1.2)
    chaos_factor = 1.2 - (state.cooperation_score / 50)
    instability_factor = 1 + (10 - state.stability) / 20
    act_multiplier = 1.2  # Act III

    shared_sigma = base_sigma * chaos_factor * instability_factor * act_multiplier

    # Symmetric noise application with renormalization
    noise = random.gauss(0, shared_sigma)

    vp_a_raw = ev_a + noise
    vp_b_raw = ev_b - noise  # Symmetric: both move together

    # Clamp both, then renormalize to sum to 100
    vp_a_clamped = clamp(vp_a_raw, 5, 95)
    vp_b_clamped = clamp(vp_b_raw, 5, 95)

    total = vp_a_clamped + vp_b_clamped
    vp_a = vp_a_clamped * 100 / total
    vp_b = vp_b_clamped * 100 / total

    return vp_a, vp_b
```

### 4.4 Settlement Protocol

Available after Turn 4 unless Stability ≤ 2.

**Core Principle**: Settlement proposals REPLACE your strategic action for that turn. You cannot both negotiate AND play the scheduled matrix game. A day spent negotiating is a day not spent fighting.

#### 4.4.1 Settlement Proposal Structure

Each settlement proposal includes:

1. **Numeric Offer**: VP split (e.g., "I propose 55-45 in my favor")
2. **Argument Text**: Free-form text explaining your rationale (max 500 characters)

**Example Proposal**:
```
Offer: 55 VP for me, 45 VP for you
Argument: "Our positions are roughly equal, but I've demonstrated
consistent good faith throughout. The current risk level threatens
us both - a fair settlement now protects our mutual interests better
than continued brinkmanship."
```

**Argument Evaluation**: The opponent (whether human, LLM persona, or deterministic AI) reads and considers the argument. Even deterministic opponent types use an LLM to evaluate settlement arguments, as persuasion and framing matter in negotiation.

#### 4.4.2 Offer Constraints

```
Position_Difference = Your_Position − Opponent_Position
Cooperation_Bonus = (Cooperation_Score − 5) × 2

Your_Suggested_VP = 50 + (Position_Difference × 5) + Cooperation_Bonus

Constraints:
  Your_Min_Offer = max(20, Your_Suggested_VP - 10)
  Your_Max_Offer = min(80, Your_Suggested_VP + 10)
```

#### 4.4.3 Negotiation Protocol (One Counteroffer Rule)

```
SINGLE PROPOSER CASE:
  1. Proposer offers X VP + argument text
  2. Recipient may:
     - ACCEPT → Game ends at (X, 100-X)
     - COUNTER with Y VP + counter-argument
     - REJECT with explanation → Game continues, Risk +1

  3. If COUNTER:
     Proposer may:
     - ACCEPT counter → Game ends at (100-Y, Y)
     - FINAL OFFER of Z VP + final argument

  4. If FINAL OFFER:
     Recipient may:
     - ACCEPT → Game ends at (Z, 100-Z)
     - REJECT → Game continues, Risk +1

SIMULTANEOUS PROPOSAL CASE:
  Both players propose settlement in same turn:
  → Player with higher Position becomes "Proposer"
  → Player with lower Position becomes "Recipient"
  → Proceed as Single Proposer Case
  → Ties: randomly assign roles

Maximum exchanges: Offer → Counter → Final Offer (3 total)
```

#### 4.4.4 Failed Settlement and Scenario Branching

When settlement fails (rejected at any stage):

1. **Risk +1**: The failed negotiation increases tension
2. **Turn is consumed**: The scheduled matrix game is NOT played
3. **Scenario follows `default_next` branch**: Each turn in the scenario tree specifies a default branch for non-resolution outcomes

**Scenario Structure**:
```json
{
  "turn": 5,
  "matrix_type": "CHICKEN",
  "narrative_briefing": "The border standoff continues...",
  "settlement_available": true,
  "branches": {
    "CC": "turn_6_deescalation",
    "CD": "turn_6_tension",
    "DC": "turn_6_tension",
    "DD": "turn_6_crisis"
  },
  "default_next": "turn_6_tension",
  "settlement_failed_narrative": "Your diplomatic initiative collapsed. The underlying crisis remains unresolved, and tensions have risen."
}
```

**Rationale**: The `default_next` branch typically follows the "tension" or "stalemate" outcome—failed negotiation isn't de-escalation (CC) or mutual destruction (DD), but continued unresolved conflict.

#### 4.4.5 Information Revealed by Settlement

Failed settlement proposals reveal information to your opponent:
- Your numeric offer reveals your assessment of relative positions
- Your argument may reveal strategic priorities or concerns
- This information cost is part of the settlement gamble

**Design Rationale**: The one-counteroffer rule prevents endless negotiation while allowing meaningful back-and-forth. The Risk +1 penalty for rejection creates pressure to reach agreement rather than fish for information. The argument field adds a persuasion dimension that pure numbers cannot capture.

### 4.5 Deterministic Endings

| Trigger | Result |
|---------|--------|
| Risk = 10 | Mutual Destruction: both receive 20 VP |
| Position = 0 | That player loses: 10 VP. Opponent: 90 VP |
| Resources = 0 | That player loses: 15 VP. Opponent: 85 VP |

### 4.6 Crisis Termination (Probabilistic)

Starting Turn 10, at the END of each turn:

```
if Risk_Level > 7:
    P(Crisis_Termination) = (Risk_Level - 7) × 0.08
    if random() < P(Crisis_Termination):
        trigger Final_Resolution
```

| Risk Level | P(Termination per Turn) |
|------------|------------------------|
| 7 or below | 0% |
| 8 | 8% |
| 9 | 16% |
| 10 | 100% (automatic mutual destruction) |

**Maximum Turn Range**: 12-16 turns (unknown to players)

**Why This Eliminates Backward Induction**:

At Risk 8, starting Turn 10:
- P(reaching Turn 12) = 85%
- P(reaching Turn 14) = 72%
- P(reaching Turn 16) = 61%

At Risk 9:
- P(reaching Turn 12) = 70%
- P(reaching Turn 14) = 49%
- P(reaching Turn 16) = 35%

Players cannot plan "defect on last turn" because they don't know which turn is last. However, termination probabilities are low enough that strategic planning remains meaningful.

---

## Part V: Stability Update Rules

### 5.1 Definition of "Switch"

A player "switches" if their action type this turn differs from their action type last turn.

- Turn 1: No previous action, no switch possible
- Turn 2+: Compare current action type (C or D) to previous action type

### 5.2 Stability Update (Decay-Based)

Stability uses a decay-based formula that weights recent consistency more heavily:

```
At the end of each turn (Turn 2+):
  switches = count of players who switched this turn (0, 1, or 2)

  # Decay toward neutral (5)
  stability = stability × 0.8 + 1.0

  # Apply consistency bonus or switch penalty
  if switches == 0:
      stability += 1.5
  elif switches == 1:
      stability -= 3.5
  else:  # switches == 2
      stability -= 5.5

  stability = clamp(stability, 1, 10)
```

| Switches | Effect |
|----------|--------|
| 0 (both consistent) | +1.5 after decay |
| 1 (one switched) | -3.5 after decay |
| 2 (both switched) | -5.5 after decay |

### 5.3 Why This Discourages "Cooperate Then Defect"

**Trajectory: Consistent Cooperator (9 turns of C)**

| Turn | Stability |
|------|-----------|
| Start | 5.0 |
| After T2 | 6.5 |
| After T5 | 9.2 |
| After T9 | 10.0 |
| Final | Instability Factor = 1.0 |

**Trajectory: Fake Cooperator (8C then D)**

| Turn | Stability |
|------|-----------|
| Start | 5.0 |
| After T8 | 10.0 |
| After T9 (switch!) | 5.5 |
| Final | Instability Factor = 1.23 |

**Trajectory: Early Defector (2D then 7C)**

| Turn | Stability |
|------|-----------|
| Start | 5.0 |
| After T2 (D) | 5.5 |
| After T3 (switch to C) | 2.9 |
| After T9 | 9.9 |
| Final | Instability Factor = 1.0 |

**Key Properties**:
1. **Decay toward neutral**: Old consistency fades; recent behavior matters more
2. **Late defection is costly**: Switching late destroys accumulated stability
3. **Recovery is possible**: Early defectors can rebuild through consistent behavior
4. **Consistent defectors are stable**: A player who always defects has the same stability as one who always cooperates—predictability is rewarded regardless of strategy

---

## Part VI: Scenario Structure

### 6.1 Three-Act Structure

| Act | Turns | Stakes | Typical Games | Narrative Function |
|-----|-------|--------|---------------|-------------------|
| I (Setup) | 1–4 | Low (0.7× deltas) | Coordination, Stag Hunt, early PD | Establish positions, learn opponent |
| II (Confrontation) | 5–8 | Standard (1.0×) | Chicken, Inspection, Signaling | Direct conflict, testing |
| III (Resolution) | 9–end | High (1.3× deltas) | War of Attrition, Ultimatum, high-stakes Chicken | Endgame, settlement attempts |

### 6.2 Pre-Generated Scenarios

Scenarios are generated by LLM before gameplay and validated for balance. Each scenario includes:

1. **Setting**: Theme, time period, stakes
2. **Arc structure**: Which turns are escalation points vs. breathing room
3. **Branch conditions**: How outcomes determine narrative paths
4. **Matrix assignments**: Which game theory structure applies each turn
5. **State deltas**: Position/Resource/Risk changes for each outcome
6. **Narrative snippets**: Briefings and outcome descriptions
7. **Uncertain length**: Total turns is 12–16, unknown to players

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

**Instability Factor** (linear formula: 1 + (10-Stability)/20):

| Stability | Instability Factor |
|-----------|-------------------|
| 10 | 1.00 |
| 9 | 1.05 |
| 8 | 1.10 |
| 7 | 1.15 |
| 6 | 1.20 |
| 5 | 1.25 |
| 4 | 1.30 |
| 3 | 1.35 |
| 2 | 1.40 |
| 1 | 1.45 |

### 7.2 Cooperation Score Effects

**Chaos Factor** (formula: 1.2 - Coop/50):

| Score | Chaos Factor | Settlement Bonus |
|-------|--------------|------------------|
| 10 | 1.00 | +10 VP floor for both |
| 8 | 1.04 | +6 |
| 6 | 1.08 | +2 |
| 5 | 1.10 | 0 |
| 4 | 1.12 | −2 |
| 2 | 1.16 | −6 |
| 0 | 1.20 | −10 |

### 7.3 Crisis Termination Probabilities

**Starting Turn 10** (formula: (Risk-7)×0.08 for Risk>7):

| Risk Level | P(Termination/Turn) | P(Reaching Turn 14 from Turn 10) |
|------------|--------------------|---------------------------------|
| 7 or below | 0% | 100% |
| 8 | 8% | 72% |
| 9 | 16% | 49% |
| 10 | 100% | 0% (immediate destruction) |

### 7.4 Example Variance Scenarios

| Scenario | Risk | Coop Score | Stability | Act | Shared_σ |
|----------|------|------------|-----------|-----|----------|
| Peaceful early game | 3 | 7 | 8 | I | ~10 |
| Neutral mid-game | 5 | 5 | 5 | II | ~19 |
| Tense late game | 7 | 3 | 6 | III | ~27 |
| Chaotic crisis | 9 | 1 | 2 | III | ~37 |

---

## Part VIII: Player-Facing Rules

### How the Game Works

You and your opponent face a series of strategic dilemmas over 12–16 turns. Each turn, you choose from a menu of actions. Your choices and your opponent's choices are resolved using game theory—the outcome depends on what BOTH of you do.

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

**Stability Update** (decay-based):
- Stability naturally decays toward neutral (5) each turn
- Both players consistent: +1.5 after decay (builds steadily)
- One player switches: -3.5 after decay (significant penalty)
- Both players switch: -5.5 after decay (severe penalty)

**Why it matters**: When the game ends, your outcome depends on your Position AND on variance. Higher Stability = lower variance = more predictable outcomes. Recent consistency matters more than old consistency—you can't "bank" stability from early turns.

### How the Game Ends

**Settlement (you control this)**:
After Turn 4, either player can propose a settlement. If both agree on terms, the game ends with certain VP. This is the only way to guarantee your outcome.

**Crisis Termination (partially controlled)**:
Starting Turn 10, if Risk > 7, there's a chance each turn that the situation spirals out of control:
- Risk 8: 8% per turn
- Risk 9: 16% per turn
- Risk 10: Automatic Mutual Destruction

**Elimination**:
If your Position or Resources hit 0, you lose immediately.

**Natural End**:
The game has a maximum length between 12 and 16 turns. You don't know exactly when.

### Strategic Implications

**If you're ahead**: Stability is your friend. Keep things predictable. Propose settlement to lock in your advantage. Don't give your opponent the chaos they need.

**If you're behind**: Chaos might be your hope. High variance creates upset potential. But destabilizing the situation helps your opponent's variance too—you're creating a coin flip, not a sure thing.

**The key insight**: Variance is symmetric. If you destabilize things, BOTH players face more uncertainty. The question is whether your Position advantage or the variance dominates.

**You cannot plan "defect on the last turn"** because you don't know which turn is last. Starting Turn 10, if Risk > 7, any turn might be your last. Plan accordingly.

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

## Appendix B: Balance Simulation Tool

The game mechanics can be validated using the balance simulation tool at:

```
scripts/balance_simulation.py
```

**Usage**:
```bash
# Run with default settings (500 games per pairing)
uv run python scripts/balance_simulation.py

# Run with custom game count and seed
uv run python scripts/balance_simulation.py --games 1000 --seed 42
```

**Implemented Strategies**:
- TitForTat: Cooperate first, then mirror opponent
- AlwaysDefect: Always defect
- AlwaysCooperate: Always cooperate
- Opportunist: Defect when ahead, cooperate when behind
- Nash: Play Nash equilibrium (defect), with risk-awareness

**Key Simulation Results** (validated mechanics):
- No dominant strategy (no strategy exceeds 65% overall win rate)
- Average game length: ~11 turns
- Elimination rate: ~33% (position or resources hit 0)
- Mutual destruction rate: ~20% (risk hits 10)
- Games reaching max turns: ~47%

These results confirm the state delta constraints produce balanced gameplay.

---

*Document Version: 1.1*
*Last Updated: January 2026*
