# Designing and sequencing one practice question for a self-studying IB Chemistry HL student

Reading key used throughout: **[FT]** = I read the paper's full text. **[ABS]** = abstract or publisher record only. **[SEC]** = secondary source or search snippet; check against the paper before relying on it. Very little of this evidence is from chemistry or from a 16-19-year-old self-studying alone; most is maths, general-knowledge text or undergraduate lab work. Effects are not additive across techniques. Almost none of the studies tests a single-learner, self-paced flashcard-style card.

## Worked examples and fading: when should the solution come first, and how should it fade?

### Takeaway
Worked examples beat unsupported problem solving by about g = 0.48 in maths, but against tutored problem solving (the closer analogue of a card with hints and feedback) the main gain is time, not learning. The one chemistry anchor found: equal learning in 21% less time. Fading should be adaptive and step-level rather than on a fixed schedule.

### Cited Findings
- **Barbieri et al. 2023, maths, elementary to postsecondary:** 43 articles, 55 studies, 181 effects, g = 0.48 (p = .01) with robust variance estimation; medium whether used for practice or for initial skill acquisition. **[ABS]** — [Barbieri et al. 2023](https://doi.org/10.1007/s10648-023-09745-1)
- Correct examples alone gave larger effects than incorrect alone or correct-plus-incorrect (no numbers in the abstract). **[ABS]** — [Barbieri et al. 2023](https://doi.org/10.1007/s10648-023-09745-1)
- Adding self-explanation prompts moderated the effect negatively; authors say prompts "may not be a fruitful design modification". This is a between-study moderator, not a randomised contrast. It conflicts with the Atkinson and Bisra findings below. **[ABS]** — [Barbieri et al. 2023](https://doi.org/10.1007/s10648-023-09745-1)
- **Crissman 2006** is a dissertation meta-analysis that exists; I found only a blog stating Hattie took d = 0.57 from it, with no moderators. **[SEC]** — [ProQuest record](https://www.proquest.com/pagepdf/305275876); [Visible Learning blog](https://visablelearning.blogspot.com.au/p/worked-examples.html)
- **Chemistry, McLaren, Lim and Koedinger 2008, Stoichiometry Cognitive Tutor:** across three studies, students given worked examples did not learn more than pure tutored problem solving, but used 21% less time on the same problem set. As described by a later paper. **[SEC, read in Weitz et al.]** — [Weitz et al. 2010](https://escholarship.org/uc/item/31r4s7c7). The materials were used in in vivo studies with a university and three high schools. **[SEC]** — [LearnLab wiki](https://learnlab.org/wiki/index.php?oldid=8825)
- **Statistics, college, N = 84:** worked example-tutored problem pairs vs pure conditions: learning in all conditions, no significant differences, worked examples need significantly less time. **[FT]** — [Weitz et al. 2010](https://escholarship.org/uc/item/31r4s7c7)
- **Chemistry, introductory college:** quizzes with embedded worked examples and self-explanation prompts were used, were perceived as helpful and improved performance; no effect size retrieved. **[SEC]** — [Crippen and Earl 2004 record](https://mail.editlib.org/p/12876)
- **Fading:** fading worked-out steps reliably helps near transfer compared with example-problem pairs; Atkinson et al. combined fading with prompts to identify the principle at each worked step. A far-transfer caveat appeared in one excerpt with uncertain attribution. No effect size retrieved. **[ABS]** — [Atkinson, Renkl and Merrill 2003](https://asu.elsevierpure.com/en/publications/transitioning-from-studying-examples-to-solving-problems-effects-/)
- **Adaptive vs fixed fading, Geometry Cognitive Tutor, lab and classroom:** better gains with adaptive than fixed fading, and fixed than problem solving alone. A second summary of the same record says fixed fading and problem solving did not differ in the classroom, so check the full text; no effect sizes retrieved. **[ABS]** — [Salden et al. 2010](https://link.springer.com/doi/10.1007/s11251-009-9107-8); [second summary](https://www.bohrium.com/paper-details/the-expertise-reversal-effect-and-worked-examples-in-tutored-problem-solving/811838108407431172-11376)
- **Step difficulty matters:** the worked-example effect was strongest at the hardest step, shrank towards the easiest, and vanished for more knowledgeable participants (mathematics). **[SEC]** — [Chen, Retnowati and Kalyuga 2018](https://repository.lboro.ac.uk/articles/journal_contribution/The_effect_of_worked_examples_on_learning_solution_steps_and_knowledge_transfer/24459859)
- **Bottom-out hints can behave as worked examples** when students spend time on them; see the hints section. **[FT]** — [Shih, Koedinger and Scheines 2008](https://www.cmu.edu/dietrich/philosophy/docs/scheines/Shih_Koedinger_Scheines_2008_EDM.pdf)

### Inferences
- Benchmark for this app: a card with attempt, hints and feedback is closer to "tutored problem solving" than to "conventional problem solving", so do not expect the g = 0.48 from swapping in a worked example. Expect time savings on novice cards. Extrapolated from maths and a stoichiometry tutor.
- A faded card can be built from the existing Procedure: for a new question type show all steps, then all but the hardest or last step, then only the first step, then nothing. Which step to fade first is not settled (see Gaps); "keep support on the hardest step longest" is my reading of Chen et al.
- Self-explanation prompts should not be attached by default to every worked example, given the conflict with Barbieri.

### Gaps
- Could not read Barbieri's moderator tables: no CI, no fading result, no breakdown of comparison condition or grade.
- Backward vs forward fading effect sizes were not retrieved. From memory (unverified): Renkl, Atkinson and colleagues found fading better than example-problem pairs, with backward fading at least as good as forward. Treat as a lead.
- Crippen and Earl's 2007 paper in Computers and Education (recalled from memory, not confirmed by search) and the review "Applying cognitive theory to chemistry instruction: the case for worked examples" ([RSC record](https://pubs.rsc.org/en/content/articlehtml/2009/rp/b901458f), returned 403) were not read.
- No RCT found on worked examples in IB or A-level-style chemistry for ages 16-19.

## Expertise reversal: when do examples and hints start to harm, and how to detect the switch?

### Takeaway
The best available pooled numbers, from a secondary summary, suggest high structure helps low prior knowledge by about d = 0.5 and hurts high prior knowledge by about d = 0.4. So guidance should fall as mastery rises. A rapid "first step" probe is the classic detector, but I could only confirm its existence, not its validity figures.

### Cited Findings
- **Tetzlaff et al. 2025 meta-analysis:** 60 studies, 176 effects, about 6,000 participants. Low prior knowledge: d = 0.505 favouring high-structure instruction. High prior knowledge: d = -0.428 favouring low structure. Effect grows with age, strongest in higher education, smaller in language and humanities, thin primary evidence. **[SEC, blog summary; primary paper not accessible]** — [Learning and the Brain summary](https://www.learningandthebrain.com/blog/one-size-doesnt-fit-all-teaching-experts-and-novices/); [DOI](https://doi.org/10.1016/j.learninstruc.2025.102142)
- Definition and background review: reversal of relative effectiveness of methods as domain knowledge changes. **[ABS]** — [Kalyuga 2007](https://www.doi.org/10.1007/S10648-007-9054-3)
- **Geometry experiments:** worked examples beat generation for high element-interactivity material; generation beat worked examples for low-interactivity material; as expertise rose the interaction disappeared and generation won for all materials. **[SEC]** — [Chen, Kalyuga and Sweller 2015](https://next.sciencegate.app/document/10.1037/edu0000018). High school trigonometry replication in a 2 x 2 x 2 design; effects more likely on delayed than immediate tests. **[SEC]** — [Chen, Kalyuga and Sweller 2016](https://repository.lboro.ac.uk/articles/journal_contribution/Relations_between_the_worked_example_and_generation_effects_on_immediate_and_delayed_tests/12052686)
- **Other guidance reverses too:** signalling r = 0.19 for low prior knowledge, r = -0.08 for high. Removing seductive details g = 0.52 for those without prior experience. **[FT, table in Noetel]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Detection:** rapid dynamic assessment evaluates what is in working memory (schemas retrieved) using quick tests combined with load measures, used to tailor guidance in adaptive e-learning; linear equations and kinematics tutorials lowered guidance as expertise rose. **[SEC]** — [Kalyuga and Sweller 2005 record](https://data.zhenzhi.com/details/1/887226768); [book chapter citing first-step and rapid verification methods](https://www.springerpflege.de/chapter/10.1007/978-1-4419-8126-4_13)

### Inferences
- A cheap two-stage check suits this app: one tap "what would you do first?" before options on a new item family, plus a confidence tap. Correct and confident twice running means drop the guidance layer; a wrong first step means offer the faded example.
- Harm at high knowledge is relative. Hints that are optional and ignored should not impose the same redundancy cost as forced ones, but this is not tested in the studies I read. Keep them collapsed rather than visible.
- For a motivated HL student the likely position differs by topic, so mastery must be per sub-topic or per question type, not per student. Inference from the prior-knowledge moderator; no direct test.

### Gaps
- Tetzlaff's CIs, heterogeneity and whether specific hints (not just instruction format) reverse: not obtained. The elsevier link did not render.
- First-step validity correlations with long tests: I recall Kalyuga and Sweller reporting high correlations, unverified here.
- No threshold found for when a learner "switches". Prior knowledge is a continuum per the Tetzlaff summary.

## Attempt first or instruction first?

### Takeaway
Attempting before the answer helps memory for that exact content (prequestions g = 0.54), even with errors, and does not generalise much to other content (g = 0.04). Productive failure supports attempt-first for conceptual learning of new ideas, but only when followed by proper instruction, and it conflicts with cognitive-load results on high-complexity material. The contexts differ: most of this concerns new material, not exam practice on content already met.

### Cited Findings
- **St. Hilaire, Chan and Ahn 2024 preregistered meta-analysis of prequestions (no feedback during prequestions):** specific effect g = 0.54 [0.42, 0.66], k = 97, bias-adjusted 0.45; general effect on untested material g = 0.04 [-0.04, 0.11], k = 91. **[FT, part]** — [St. Hilaire et al.](https://doi.org/10.3758/s13423-023-02353-8)
- Moderators of the specific effect: guessing required g = 0.65 vs not g = 0.22 (p < .001); factual g = 0.58 vs conceptual g = 0.28 (p = .073); adults g = 0.62 vs grade-school g = 0.22 (p = .020, k = 20). Moderators are correlational. Classroom translation is flagged as still to be established. **[FT, part]** — [St. Hilaire et al.](https://doi.org/10.3758/s13423-023-02353-8)
- **Pan and Sana 2021, five experiments, n = 1,573, expository text, 5 min or 48 h:** pretests beat posttests by d = 0.30 for tested and d = 0.14 for untested questions across 22 comparisons; advantage held with or without feedback, multiple choice or cued recall. They note earlier evidence, including an 8th-grade classroom science study, tilted towards posttesting, though pre-lesson quizzes there came after assigned reading. **[FT]** — [Pan and Sana 2021](https://sc-pan.github.io/pdf/PS_2021.pdf)
- Unsuccessful attempts enhance later learning even on materials guaranteeing failure. **[SEC]** — [Kornell, Hays and Bjork 2009](https://www.scientificamerican.com/article/getting-it-wrong/). The benefit came from attempting, not merely seeing the question first. **[SEC]** — [Richland, Kornell and Kao 2009](https://learninglab.uchicago.edu/Pre-Testing_files/RichlandKornellKao.pdf)
- **Sinha and Kapur 2021:** 53 studies, 166 comparisons, bias-corrected g = 0.87 favouring problem solving then instruction over the reverse; moderators favoured attempt-first by higher grade level, while grades 2-5 and domain-general skills favoured instruction first. **[SEC; full text inaccessible; see Gaps for why 0.87 is an upper figure]** — [record of Sinha and Kapur](https://ouci.dntb.gov.ua/works/4KnMgZq7); [DOI](https://doi.org/10.3102/00346543211019105)
- Attempt-first benefits were not significantly greater for procedural learning, and were weaker when fidelity to productive-failure design was not kept. **[SEC, snippet; page later returned 404]** — [UT Austin summary](https://education.utexas.edu/about/deans-office-units/office-instructional-innovation/instruction-then-problem-solving-or-vice-versa)
- **Ashman, Kalyuga and Sweller 2020, Year 5, light energy efficiency, N = 64 and N = 71:** instruction-first beat problem-solving-first on similar problems in Experiment 1 with no transfer difference; beat it on both similar and transfer problems in Experiment 2 with higher element interactivity. **[ABS]** — [Ashman et al. 2020](https://doi.org/10.1007/s10648-019-09500-5)
- **Loibl, Roll and Rummel 2017:** attempt-first works through prior-knowledge activation and gap awareness, and depends on design features, especially instruction that compares erroneous student solutions with the canonical solution. **[SEC]** — [Loibl et al. record](https://cris.iucc.ac.il/en/publications/towards-a-theory-of-when-and-how-problem-solving-followed-by-inst/)

### Inferences
- The Ashman and Sinha-Kapur conflict is less sharp than it looks: Ashman's learners are Year 5 and the meta-analysis also finds grades 2-5 favour instruction first. But Year 5 results cannot settle HL chemistry either way. This is extrapolation in both directions.
- For revision on previously taught content, "attempt first" is really retrieval practice with feedback, and it is the default. Productive failure is not the right frame unless a topic is genuinely new.
- Requiring a committed guess is the actionable moderator (0.65 vs 0.22): always make the student pick before reveal, with no "skip to answer" that bypasses it, except when the first-step check shows they have no schema.
- Because the general effect is about zero, a single attempt on a card does not teach a technique: other cards of the same type are still needed.
- Conceptual prequestion effects were smaller (0.28), so expect less for "why" items than recall items.

### Gaps
- **Sinha and Kapur:** my memory of the abstract is an unadjusted overall g of about 0.36, with 0.87 as the bias-corrected upper estimate. Not verified this session; the paper's abstract should be checked before quoting 0.87.
- **Mera 2022:** not found as a pretesting meta-analysis. Found citations to Mera et al. 2021/2022 and [Mera, Dianova and Marin-Garcia 2026](https://research.science.eus/documentos/692222c9621d0957276def3b?lang=en), without pooled effects. Chan et al. 2018 also unread.
- **St. Hilaire and Carpenter 2020:** not located through search; the citation in the research brief remains unverified.
- No chemistry-specific productive-failure trial was found for secondary students.

## Hints: on demand or proactive, gaming, bottom-out, and hint wording

### Takeaway
On-demand hints beat proactive hints in one small repeated-measures RCT (ES 0.35, wide CI), and students do often click through to the answer. The bottom-out hint is not inherently bad: time spent on it predicts learning. I found no direct test of hints as questions versus statements.

### Cited Findings
- **Razzaq and Heffernan 2010, 72 grade 8 students, algebra, ASSISTments:** mean gain 0.137 on demand vs 0.04 proactive, ES 0.35, 95% CI [0.02, 0.74], p = .04. Benefit concentrated in those who asked for many hints; no difference for low askers. Caveats: short duration, students familiar with on-demand. **[FT]** — [Razzaq and Heffernan 2010](https://web.cs.wpi.edu/~nth/pubs_and_grants/papers/2010/ITS/Razzaq%20Hints%20Is%20It%20Better%20to%20Give%20or%20Wait.pdf)
- **Inventado et al. 2018, ASSISTments RCT, slope problems, mostly grades 6-8:** progressive on-demand hints early vs bottom-out only: more problems right with hints; no differences in speed to mastery, attempts or time. The summer sample (grades 9-10, seemingly more prior knowledge) did not show the benefit and took longer. Sample accounting does not reconcile (N = 679 vs location counts). Hint requests were marked incorrect. **[FT, summary]** — [Inventado et al. 2018](https://link.springer.com/doi/10.1186/s40594-018-0107-6)
- **Hint abuse:** Geometry Cognitive Tutor study found abuse on 36% of actions (14% if rapid hint runs count as one). Students click so quickly they cannot read the hints, then stop at the bottom-out hint. **[SEC]** — [LearnLab: Help abuse](https://learnlab.org/research/wiki/index.php/Help_abuse). Cognitive Tutors reportedly now delay before bottom-out help; students also wait long and focus on the most specific hints. **[SEC]** — [Aleven, Roll, McLaren and Koedinger 2016](https://typeset.io/pdf/help-helps-but-only-so-much-research-on-help-seeking-with-3nwq0kjvus.pdf)
- **Bottom-out as worked example:** an indicator from logged time on bottom-out hints correlated about r = 0.5 with post-test and learning gain, and captured self-explanation-related behaviour. Sample in that analysis: 18 students. **[FT]** — [Shih, Koedinger and Scheines 2008](https://www.cmu.edu/dietrich/philosophy/docs/scheines/Shih_Koedinger_Scheines_2008_EDM.pdf)
- **Hints vs explanations in ASSISTments:** students randomly given a teacher-written message were reliably less likely to ask for help again, replicated next term. **[SEC]** — [ASSISTments blog](https://www.assistments.org/blog-posts/can-student-learning-improve-using-crowdsourcing-from-teachers-in-online-learning-platforms-such-as-assistments). Requesting an explanation was associated with lower next-problem performance, but heterogeneous causal estimates suggest short-term gains for higher-effort students. **[SEC]** — [EDM 2026 poster](https://educationaldatamining.org/edm2026/proceedings/2026.EDM.poster-demo-papers.433/index.html). A WPI student thesis suggests small differences between hints and explanations; treat cautiously. **[SEC]** — [WPI thesis](https://digital.wpi.edu/downloads/zg64tq423?locale=zh)
- **Questions vs statements:** an undergraduate project suggests scaffolding questions beat hints; weak evidence. **[SEC]** — [WPI student work](https://digital.wpi.edu/show/c247ds68c). Nearest analogue: self-explanation prompts as questions g = 0.559 (k = 36) vs imperatives g = 0.395 (k = 12). **[FT]** — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf)

### Inferences
- Keep hints on demand, in a ladder that gets more specific, and record use. A student with no grade at stake may still rush, so a 2-3 second gate or one-at-a-time release before the last rung is a reasonable borrowing from Cognitive Tutors, though no effect size for it was found.
- A card answered after a strong hint should not count as first-try correct for Mastered or for spacing. This mirrors Inventado's coding, but its effect on learning is not tested.
- Log time on the "I'm lost" solution; quick dismissal is the signal for gaming, not the use itself (from Shih's small sample).
- For one motivated self-chooser, Razzaq's high-asker result is encouraging, but those were 12-14-year-olds doing algebra. Extrapolation.

### Gaps
- Could not read Aleven et al. 2016 in full: no quantitative help-seeking-to-learning estimates.
- No ideal number of hint levels or optimal sequence shown experimentally in what I found.
- No direct test of question-form vs statement-form hints.
- No chemistry hint study.

## Feedback: type, timing, confidence, and distractors

### Takeaway
Elaboration matters far more than timing. Right or wrong alone does almost nothing (0.05) in computer settings, the correct answer helps some (0.32), and explanation helps more (0.49). Whether it should be immediate or delayed nets out at about zero across real classes, so show it immediately in a self-study app. Competitive distractors help learning of the related content; a direct test of showing why each one is wrong was not found.

### Cited Findings
- **Wisniewski, Zierer and Hattie 2020:** 435 studies, 994 effects, N > 61,000. Random effects d = 0.48 [0.44, 0.51] after outliers (0.55 before); I-squared 83%; 17% of effects negative. Reinforcement or punishment d = 0.24, k = 39; corrective d = 0.46, k = 238; high-information d = 0.99, k = 42. Cognitive outcomes d = 0.51, k = 597. Controlled designs d = 0.42 vs pre-post d = 0.63. Publication asymmetry in journal articles only. Timing not analysed; learner proficiency not coded. **[FT]** — [Wisniewski et al. 2020](https://www.frontiersin.org/articles/10.3389/fpsyg.2019.03087/full)
- **Van der Kleij, Feskens and Eggen 2015, computer-based, 40 studies, 70 effects:** right or wrong 0.05, correct answer 0.32, elaborated 0.49. Elaborated particularly better for higher-order outcomes. Larger in maths than science; smaller with delayed timing and in primary or high school. Timing by outcome order pattern not significant. **[SEC, abstract-level]** — [Van der Kleij et al. 2015](https://acuresearchbank.acu.edu.au/item/86y84/effects-of-feedback-in-a-computer-based-learning-environment-on-students-learning-outcomes-a-meta-analysis)
- **Kulik and Kulik 1988:** lab acquisition of test content usually favours delayed; applied classroom quizzes usually favour immediate. **[SEC]** — [Smith and Kimball 2010](https://www.ou.edu/memorylab/pdfs/SmithKimball_2010_LearningFromFeedback_ms.pdf)
- **ManyClasses 1, 38 college classes:** timing estimate 0.002, no overall effect; possible modest delayed advantages in undersampled class types. **[ABS]** — [Fyfe et al. 2021](https://scholarworks.iu.edu/dspace/items/bbf719db-91fe-4a2b-9c3b-dbf59f812bd3)
- **Conflict: Mullet et al. 2014, engineering course:** delayed feedback gave better later exam scores on new problems, even though students preferred immediate. Timing gap was days (about 4 vs 12). **[SEC]** — [Mullet et al. 2014](https://profiles.wustl.edu/en/publications/delaying-feedback-promotes-transfer-of-knowledge-despite-student-/); [timing detail](https://www.learningscientists.org/blog/2023/3/2)
- **Hypercorrection:** high-confidence errors are more likely corrected after feedback than low-confidence ones, plausibly through surprise capturing attention; replicated with young adults and children. **[SEC]** — [Duke dissertation](https://dukespace.lib.duke.edu/items/d6ab09ca-f55c-4efb-9d32-2788bc5838b2). The effect persists over a week, but high-confidence errors were more likely than low-confidence errors to recur. **[SEC]** — [2011 study](https://typeset.io/pdf/the-hypercorrection-effect-persists-over-a-week-but-high-3hxdkh7nbu.pdf)
- **Competitive distractors, Little and Bjork 2014, university participants (n = 28 and n = 96), expository text passages:** related questions whose answers had been competitive lures were recalled better than control (46% vs 37%, d = 0.43, Exp. 2) and better than noncompetitive (d = 0.45); noncompetitive lures gave no gain. Pattern held with and without feedback. Competitive lures were not more likely to intrude as errors. **[FT]** — [Little and Bjork 2014](https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2017/01/LittleBjorkMC2014.pdf)
- **Butler 2018 review:** keep formats simple; avoid "none/all of the above"; relatively few plausible options; moderate difficulty; review answers afterwards, because MC exposes students to plausible false information. **[SEC, press coverage]** — [WashU summary](https://source.washu.edu/2018/09/for-better-multiple-choice-tests-avoid-tricky-questions-study-finds/); [record](https://profiles.wustl.edu/en/publications/multiple-choice-testing-in-education-are-the-best-practices-for-a/)

### Inferences
- Feedback on a wrong answer should default to explanation, not a green or red mark. A student who opens only the verdict gets near the 0.05 end. Extrapolated from mixed subjects.
- The d = 0.99 high-information result rests on 42 effects with high overall heterogeneity. Do not promise it for this app.
- Delayed feedback is not worth the friction: spacing the next attempt gives the delayed-exposure benefit anyway. The worthwhile delay is a re-test later, not a withheld answer. Inference.
- A one-tap confidence rating before reveal has two uses: flag high-confidence errors as priority explanations, and flag low-confidence correct answers so they still get reviewed. Note the 2011 result: high-confidence errors need re-testing, not one correction.
- Past-paper lures are presumably competitive, since they come from examiners. Explanations targeted at the chosen lure fit Little and Bjork's retrieval account, though they did not test such explanations.

### Gaps
- No experiment found directly testing "explain why each distractor is wrong" vs "explain correct answer only".
- Metcalfe's 2017 review and Butler, Karpicke and Roediger 2008 on low-confidence correct answers were not read; a vendor page and passing citations support the claim only indirectly.
- Mertens and de Bruin meta-analysis of timing not found.
- No hypercorrection work in chemistry or in calculation problems was found.

## Self-explanation: how to prompt, and typed or selected?

### Takeaway
Prompted self-explanation has a robust average effect (g = 0.55), about g = 0.43 in high school and g = 0.57 in science, but much of this comes from text study and control groups given nothing. Against provided explanations it drops to 0.35. Prompts for conceptual reasons are stronger than those asking for justification or metacognition. Selected-explanation evidence conflicts.

### Cited Findings
- **Bisra et al. 2018:** 69 effects from 64 reports, N = 5,917, g = 0.552 [0.454, 0.650], I-squared 65%. **[FT]** — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf)
- By comparison: nothing extra g = 0.673, k = 41; instructional explanation g = 0.354, k = 6; other strategy g = 0.304, k = 7. **[FT]** — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf)
- By task: solving problems g = 0.476, k = 20; worked examples g = 0.362, k = 8; text g = 0.787, k = 14. By knowledge type: conceptual g = 0.598, k = 33; procedural g = 0.468, k = 3. Science g = 0.565, k = 25; maths g = 0.441, k = 16. High school g = 0.426, k = 13. Tests in MC format g = 0.410, k = 7. **[FT]** — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf)
- By prompt: conceptualise g = 0.873, k = 13; explain g = 0.678, k = 12; justify g = 0.416, k = 20; metacognitive g = 0.192, n.s., k = 3. Interrogative g = 0.559; imperative g = 0.395; fill-in g = 0.895, k = 2; multiple choice g = 0.242, n.s., k = 2. General prompts g = 0.678 and specific g = 0.510 did not differ reliably. Concurrent g = 0.521; retrospective g = 0.571. **[FT]** — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf)
- **Time cost:** g = 0.72 where self-explainers took longer, g = 0.41 where time was equal (difference n.s.). Time-on-task often unreported; authors warn efficiency may be exaggerated. **[FT]** — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf)
- **Maths meta-analysis:** small to moderate improvement in procedural, conceptual knowledge and procedural transfer. **[SEC]** — [Rittle-Johnson, Loehr and Durkin 2017](https://link.springer.com/article/10.1007/s11858-017-0834-z). Near-transfer g = 0.39 and thin long-term retention evidence, per one secondary summary. **[SEC]** — [ID Tips](https://idtips.substack.com/p/self-explanation-the-evidence-behind)
- **In a tutoring system:** students explaining steps in a Cognitive Tutor learned with greater understanding and did better on transfer problems, in two classroom experiments. **[SEC]** — [Aleven and Koedinger 2002](https://serc.carleton.edu/resources/40402.html). **Menu vs dialogue, 71 advanced students:** no overall learning difference, but dialogue students better at stating explanations. **[SEC, truncated snippet]** — [Geometry Explanation Tutor evaluation](https://typeset.io/pdf/evaluating-the-effectiveness-of-a-tutorial-dialogue-system-1gwtxn8o0i.pdf)
- **Selecting from a list, conflict with Bisra's MC result:** selecting reasons during a circuit game gave better embedded transfer than no self-explanation, d = 1.20. **[SEC]** — [Johnson and Mayer 2010](https://www.datalearner.com/academic/journal-papers/0747-5632/volumes-and-issues/121/paper-detail/33903)
- **Provided explanations:** benefits of instructional explanations in example-based learning are "minimal" overall, greater for conceptual than procedural knowledge, not clearly superior to self-explaining. **[ABS]** — [Wittwer and Renkl 2010](https://link.springer.com/doi/10.1007/s10648-010-9136-5)

### Inferences
- A short interrogative prompt about the chemistry itself ("why does the stronger acid have the lower pKa?") is best supported, not "how confident are you?" as a substitute for explanation. Metacognitive prompts are the weakest category, though with k = 3.
- Keep prompts rare: only after an error or a low-confidence correct answer. Bisra's time issue and Barbieri's negative moderator both argue against prompting every card.
- Selected explanations are cheap but weakly supported in Bisra (k = 2). Johnson and Mayer's game context does not transfer cleanly. Best compromise: a typed one-liner on key cards, a menu of chemistry reasons on routine ones, and the fill-in format is worth trying (k = 2, so very tentative).
- Wittwer and Renkl plus Bisra together imply the "Procedure" panel will not do much alone. The student has to do something with it.

### Gaps
- No clean head-to-head of typed vs selected self-explanation in chemistry.
- Wittwer and Renkl's numeric effect was not retrieved. I recall about g = 0.16, unverified.
- Chi's original studies and McEldoon et al. 2013 ("Is self-explanation worth the time?") were not read; the latter's comparison to extra practice would directly bear on time cost.

## Cognitive load: split attention, redundancy, coherence, signalling, and amount on screen

### Takeaway
Keep related information together (g = 0.63-0.74), cue the key step (g = 0.43), cut interesting but irrelevant material (g = 0.33) and chunk (g = 0.34). These all come mainly from multimedia lessons, and Noetel found good design matters less in self-paced settings and more for complex material. I found no experiment on progressive disclosure as such, and no numeric limit on text.

### Cited Findings
- **Noetel et al. 2022:** 29 reviews, 1,189 studies, 78,177 participants; 11 principles with positive effects on learning; design matters more for complex materials and system-paced than self-paced settings. **[FT]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Contiguity, split attention:** overall g = 0.74 [0.67, 0.82], k = 46; spatial g = 0.63 [0.55, 0.71], k = 58; temporal g = 0.78, k = 13. Example: labels on a diagram, not in a legend. **[FT]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Signalling:** g = 0.43 [0.35, 0.50], k = 209; load reduction g = 0.25; transfer g = 0.53, retention g = 0.33. Low prior knowledge benefits more. **[FT]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Segmenting:** g = 0.34 [0.30, 0.38], k = 123; load g = 0.23. Instructor-segmented g = 0.41 vs learner-segmented g = 0.20; takes longer (g = 0.92 on time). **[FT]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Removing seductive details:** g = 0.33, k = 58; persistently on-screen details g = 0.43; no prior experience g = 0.52. **[FT]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Verbal redundancy:** g = 0.15 overall; adding text to audio g = 0.29; adding audio to text g = -0.04. This concerns narration, not duplicate on-screen panels. **[FT]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)
- **Progressive disclosure:** only UX and e-learning guidance found, not experiments. **[SEC]** — [Uxcel glossary](https://app.uxcel.com/glossary/progressive-disclosure). A learner-controlled worked example study (N = 98, maths) was located but its findings were not retrieved. — [MDPI 2024](https://www.mdpi.com/2227-7102/14/6/597)

### Inferences
- Progressive disclosure is defensible by analogy to segmenting, but the g = 0.20 for learner-segmented vs g = 0.41 for designer-segmented suggests the designer should set the order and default, not hand the student six equal buttons.
- Apply contiguity directly: put the why-wrong note beside the chosen option, and mark data-booklet values in the worked step rather than in a separate panel. This is likely the largest cheap gain, though measured on multimedia rather than MC cards.
- Treat the Syllabus panel as a potential seductive detail while answering or reviewing an error. It can stay reachable but should not be persistent.
- Signalling for a high-knowledge learner may do nothing or slightly harm. Fade highlights with mastery.

### Gaps
- No evidence for a specific word or line limit per card.
- No progressive disclosure RCT on an MC card.
- Sweller's split-attention primary studies and Mayer's books were not read directly; Noetel was used as the umbrella.

## Dual coding, drawing and interactive diagrams

### Takeaway
Generating a drawing helps comprehension relative to only reading, and animation modestly beats static pictures. No result was found for interactive vs static chemistry diagrams.

### Cited Findings
- **Fiorella and Zhang 2018:** against reading only or text-focused strategies, drawing consistently improved comprehension and transfer regardless of guidance; against model-focused strategies or provided illustrations, results were mixed. Science text. **[ABS]** — [Fiorella and Zhang 2018](https://ecrhub.org/publications/drawing-boundary-conditions-learning-drawing)
- **Hoffler and Leutner 2007:** 26 studies, 76 comparisons, d = 0.37 for animation over static; larger when representational, highly realistic, and for procedural-motor knowledge. **[SEC]** — [Hoffler and Leutner record](https://www.leibniz-ipn.de/en/research/publications/instructional-animation-versus-static-pictures-a-meta-analysis)
- **Berney and Betrancourt 2016:** g = 0.23, k = 61 as tabulated; factual g = 0.336 vs conceptual g = 0.162. **[FT, table in Noetel]** — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329)

### Inferences
- For curly arrows, Lewis structures and shapes, "draw it on paper, then compare" is low-cost and reasonably supported by analogy, though not tested on exam-style items. Use it on selected concepts, not every card, because it takes time.
- Animation is a poor priority for the app: small, shrinking effect, and costly to make.
- Clickable cycles (already in the Criteria tile) are untested by these sources. Do not assume the animation effect carries over.

### Gaps
- Hoffler and Leutner compare animation with static, not interactive with static. No interactive-vs-static meta-analysis was found.
- Chemistry-specific representation work (Rau, Wu) could not be located with my searches.

## Teaching tricks, shortcuts and elimination directly

### Takeaway
I found no pooled effect for test-wiseness or elimination training. Small studies show test-taking skills can be trained, while chemistry studies show that shortcut heuristics used without understanding often mislead. Teach elimination as content reasoning, attach each trick to conditions of use, and don't treat this as an evidence-backed effect size.

### Cited Findings
- **Test-wiseness is trainable, in single studies:** a 2 x 2 study of 252 students crossing subject knowledge with training found training improved performance. **[SEC]** — [IPN record](https://www.leibniz-ipn.de/en/research/publications/test-wiseness-ein-unterschatztes-konstrukt). Sixty randomly assigned fourth-graders in Trinidad scored higher after a test-wiseness unit. **[SEC]** — [UWI study](https://uwispace.sta.uwi.edu/bitstreams/413a7953-5cb0-4041-a36d-3651d3b4627f/download)
- **Moderators:** not all examinees gain; depends on attitude, training length, prior knowledge and metacognition. **[SEC]** — [SAGE encyclopedia entry](https://methods.sagepub.com/ency/edvol/embed/sage-encyclopedia-of-educational-research-measurement-evaluation/chpt/testwiseness)
- **Test preparation meta-analysis** (Hao, Baird, El Masri and Double) lumps coaching, familiarisation and test-wiseness, so it does not isolate these; full text returned 403. **[SEC]** — [Oxford record](https://ora.ox.ac.uk/objects/uuid:de68c5d5-26a9-4450-be0d-949e563788a4/files/rhh63sx997)
- **Chemistry heuristics:** undergraduates ranking substances relied on recognition, representativeness, one-reason decision making and arbitrary trends, and this often led them astray. **[ABS]** — [Maeyer and Talanquer 2010](https://zendy.io/title/10.1002/sce.20397). Predicting reactivity: over-reliance on variable reduction and recognition memory. **[ABS]** — [Maeyer and Talanquer 2013](https://zendy.io/title/10.1002/tea.21092)
- Talanquer recommends building metacognitive awareness and analytical reasoning rather than suppressing intuition. **[ABS]** — [RSC chapter](https://books.rsc.org/books/monograph/2512/chapter/8886498/Controlling-Heuristic-Reasoning)
- **Procedural and conceptual knowledge are bidirectional in maths**, so procedures do not have to wait for full understanding, and each supports the other. **[SEC]** — [Rittle-Johnson, Schneider and Star 2015](https://moodle2.units.it/pluginfile.php/574613/mod_resource/content/2/s10648-015-9302-x.pdf); [Schneider et al. 2011](https://www.uni-trier.de/fileadmin/fb1/prof/PSY/PAE/Forschung/SchneiderEtAl2011.pdf)
- **Mechanism support for content-based elimination:** discriminating among competitive options drives retrieval about all of them. **[FT]** — [Little and Bjork 2014](https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2017/01/LittleBjorkMC2014.pdf)

### Inferences
- Distinguish chemistry-grounded elimination ("the units or sign rule this out because...") from test-form cues (longest answer, odd one out). The first builds on Little and Bjork's retrieval account. The second is unsupported here, and Butler's advice about well-built items suggests it may not pay off on good exams.
- Show a trick after the student has seen why it works, together with "when it fails". The Maeyer and Talanquer results imply that a heuristic without boundaries becomes the error. Whether derive-first beats tell-first for tricks is untested in what I found; the bidirectional result means telling first is not clearly harmful.
- A useful test of a trick card: give one item where the shortcut gives the wrong answer. This is my suggestion, not a tested intervention.

### Gaps
- No meta-analysis specific to elimination strategy instruction was found. Scruggs, White and Bennion 1986 and Bangert-Drowns et al. 1983 exist ([Scruggs record](https://scilit.com/publications/e88d7cd259a27143538dbabe1d0a68ef)), but their effects were not retrieved and they target younger learners or broad coaching.
- Nakhleh's algorithmic vs conceptual chemistry work was not retrieved. The "inert procedure" risk rests on theory and adjacent findings, not an RCT I could cite.

## Judging the current card: what should come first, and how much help?

### Takeaway
The current order (attempt with optional help, then reveal) is well supported as a default for content already met. The evidence points to five changes: force a commitment, stage the help, replace equal tabs with one designer-set explanation, adapt to prior knowledge, and add one small generative act only on errors or shaky successes. These are inferences, with cited anchors below.

### Cited Findings
| Design element | Best anchor | Strength for this learner |
|---|---|---|
| Commit to an answer before reveal | Prequestion specific effect g = 0.54; guessing g = 0.65 vs 0.22 — [St. Hilaire et al.](https://doi.org/10.3758/s13423-023-02353-8) | Moderate; not chemistry, no feedback in the studies |
| Worked example first for novices | Low prior knowledge favoured by structure d = 0.505 — [summary of Tetzlaff et al.](https://www.learningandthebrain.com/blog/one-size-doesnt-fit-all-teaching-experts-and-novices/) | Moderate; secondary source |
| Save time with examples | 21% less time in stoichiometry tutor, no learning loss — [Weitz et al. 2010](https://escholarship.org/uc/item/31r4s7c7) | Moderate; the one chemistry anchor |
| On-demand help | ES 0.35 [0.02, 0.74] — [Razzaq and Heffernan 2010](https://web.cs.wpi.edu/~nth/pubs_and_grants/papers/2010/ITS/Razzaq%20Hints%20Is%20It%20Better%20to%20Give%20or%20Wait.pdf) | Weak to moderate; one small study, ages 12-14 |
| Elaborated feedback | 0.49 vs 0.05 — [Van der Kleij et al. 2015](https://acuresearchbank.acu.edu.au/item/86y84/effects-of-feedback-in-a-computer-based-learning-environment-on-students-learning-outcomes-a-meta-analysis); d = 0.99 high-information — [Wisniewski et al. 2020](https://www.frontiersin.org/articles/10.3389/fpsyg.2019.03087/full) | Moderate to strong for direction, not for size |
| Immediate reveal | Timing estimate 0.002 — [ManyClasses 1](https://scholarworks.iu.edu/dspace/items/bbf719db-91fe-4a2b-9c3b-dbf59f812bd3) | Moderate; college classes |
| Why-wrong beside the option | Spatial contiguity g = 0.63 — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329) | Moderate as analogy |
| Designer-set reveal order | Instructor g = 0.41 vs learner g = 0.20 — [Noetel et al. 2022](https://journals.sagepub.com/doi/10.3102/00346543211052329) | Weak to moderate as analogy |
| One conceptual prompt | Conceptualise g = 0.873, science g = 0.565, high school g = 0.426 — [Bisra et al. 2018](https://www.Gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf); opposing moderator — [Barbieri et al. 2023](https://doi.org/10.1007/s10648-023-09745-1) | Moderate; conflicting |
| Tricks tab | No pooled effect; heuristics mislead — [Maeyer and Talanquer 2010](https://zendy.io/title/10.1002/sce.20397) | Weak |

### Inferences
**Before answering**
- Keep the attempt first. Add a route for "never seen this": a faded worked example instead of a blind guess, chosen by the first-step probe or "I'm lost", because forced failure with no schema is where the novice evidence applies.
- Rework six equal buttons into a ladder, least to most revealing: Command term or Time (orientation), Data booklet (resource), Disguise (recasts the problem), Eliminate (narrows answers), I'm lost (faded example, ends with a retry on a twin or the same step).
- Eliminate is the button most at risk. If it removes options, it does the discrimination that Little and Bjork suggest produces the benefit. Better form: a prompt to rule out one option and say why, then check. This is inference; no experiment on it.
- Count help used in the Mastered logic, and stop showing buttons by default on high-mastery cards.

**At commit**
- Require selection, plus one confidence tap (sure / unsure). Evidence for hypercorrection supports the use, but not this exact interface.

**After answering, first screen**
- Show the verdict and a two-to-three line explanation at once, including one line on the option picked if wrong. Do not make the student choose among five tabs to learn why.
- Markscheme next, because examined language matters on past papers. That rationale is practical and not from these studies.
- Procedure collapsed for correct-and-sure answers, open by default after errors. Syllabus available but quiet. Tricks only after Procedure, with "when it fails".

**Then**
- On errors and unsure-correct answers only: one interrogative "why" prompt, typed one line, or a re-attempt at the step that failed, with a later re-test of the same idea on a different item. The general prequestion effect of about zero means the transfer has to be practised, not assumed.

**Size of expected gain**
- Do not add these effect sizes. A realistic honest expectation is "moderate, unmeasured", and the app can test itself: log first-try accuracy on twin items after a gap, comparing cards with and without a given feature. A single learner gives noisy data, so only large differences would be readable.

### Gaps
- No study was found that tests a complete sequence like this for one chemistry MC item or for IB. The design is assembled from separate lines of evidence.
- Evidence on spacing, interleaving and retrieval across cards belongs to adjacent research and is outside these notes.
- Motivation effects of forcing commitment, or of removing buttons, were not studied here. A self-chooser who dislikes the friction may stop using the app, which no effect size above captures.
