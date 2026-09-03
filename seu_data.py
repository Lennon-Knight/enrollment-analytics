import os
import random
from datetime import date
from sqlalchemy import create_engine, text

random.seed(42)

DB_URL = f"postgresql+psycopg://seu_analytics:{os.environ['PGPASSWORD']}@localhost:5432/seu_enrollment"
engine = create_engine(DB_URL)

# ==========================================================================
# ASSUMPTIONS — must match assumptions.md
# ==========================================================================

# first-year retention target per major (before modifiers)
MAJOR_RETENTION = {
    "Nursing":            0.85,
    "Business":           0.80,
    "Education":          0.80,
    "Ministry":           0.78,
    "Psychology":         0.76,
    "Computer Science":   0.74,
    "Math":        0.70,
}
MAJOR_WEIGHTS = [0.18, 0.22, 0.12, 0.10, 0.14, 0.12, 0.12]

COMMUTER_PENALTY   = 0.08   # added to departure probability
FIRST_GEN_PENALTY  = 0.06
LOW_GPA_MULTIPLIER = 2.0    # hs_gpa < 3.0
GATEWAY_FAIL_MULT  = 2.0    # failed a gateway course that year
HIGH_AID_BONUS     = 0.10   # subtracted from departure probability
HIGH_AID_THRESHOLD = 3000

# attrition falls sharply after the first year
YEAR_MULTIPLIER = {1: 1.0, 2: 0.55, 3: 0.35, 4: 0.25, 5: 0.20, 6: 0.20}

GATEWAY_DFW = 0.33          # gateway course D/F/W rate
NORMAL_DFW  = 0.12

CREDITS_TO_GRADUATE = 120
COHORT_SIZE = 320           # first-time students entering each fall
TRANSFER_SIZE = 70          # transfers entering each fall

FIRST_COHORT_YEAR = 2018
LAST_COHORT_YEAR  = 2025
LAST_TERM_YEAR    = 2026

# ==========================================================================
# COURSE CATALOG
# ==========================================================================

COURSES = [
    ("MATH", "2311", "Calculus I",              4, True),
    ("CHEM", "2045", "General Chemistry I",     3, True),
    ("BIOL", "2010", "Anatomy & Physiology I",  4, True),
    ("ENGL", "1101", "Composition I",           3, False),
    ("BIBL", "1013", "Old Testament Survey",    3, False),
    ("BIBL", "1023", "New Testament Survey",    3, False),
    ("HIST", "2010", "American History",        3, False),
    ("PSYC", "2012", "General Psychology",      3, False),
    ("COMM", "2100", "Public Speaking",         3, False),
    ("ACCT", "2021", "Financial Accounting",    3, True),
    ("CSCI", "2010", "Programming I",           3, True),
    ("MATH", "1106", "College Algebra",         3, False),
]

AID_TYPES = ["Pell Grant", "Institutional Scholarship", "Federal Loan",
             "State Grant", "Athletic Scholarship"]


def class_level(credits):
    if credits < 30:
        return "Freshman"
    if credits < 60:
        return "Sophomore"
    if credits < 90:
        return "Junior"
    return "Senior"


def pick_grade(hs_gpa, is_gateway):
    """Grade distribution shifted by preparation and course difficulty."""
    dfw_rate = GATEWAY_DFW if is_gateway else NORMAL_DFW
    if hs_gpa < 3.0:
        dfw_rate *= 1.6
    if random.random() < dfw_rate:
        return random.choices(["D", "F", "W"], weights=[35, 30, 35])[0]
    return random.choices(["A", "B", "C"], weights=[35, 40, 25])[0]


# ==========================================================================
# BUILD
# ==========================================================================

with engine.begin() as conn:
    conn.execute(text("DELETE FROM course_enrollments"))
    conn.execute(text("DELETE FROM financial_aid"))
    conn.execute(text("DELETE FROM enrollments"))
    conn.execute(text("DELETE FROM courses"))
    conn.execute(text("DELETE FROM students"))
    conn.execute(text("DELETE FROM terms"))

    # ---- terms ----------------------------------------------------------
    # term_id is sequential so terms sort; season + academic_year is what
    # makes fall-to-fall matching possible.
    terms = {}          # (year, season) -> term_id
    term_id = 1
    for year in range(FIRST_COHORT_YEAR, LAST_TERM_YEAR + 1):
        for season, census in [("Fall", (9, 15)), ("Spring", (1, 25)),
                               ("Summer", (6, 5))]:
            # spring/summer of an academic year fall in the next calendar year
            cal_year = year if season == "Fall" else year + 1
            conn.execute(
                text("""INSERT INTO terms
                        (term_id, academic_year, season, label, census_date)
                        VALUES (:id, :yr, :s, :lbl, :cd)"""),
                {"id": term_id, "yr": year, "s": season,
                 "lbl": f"{season} {cal_year}",
                 "cd": date(cal_year, census[0], census[1])}
            )
            terms[(year, season)] = term_id
            term_id += 1

    # ---- courses --------------------------------------------------------
    course_ids = []
    for subj, num, title, hrs, gateway in COURSES:
        cid = conn.execute(
            text("""INSERT INTO courses
                    (subject_code, course_number, title, credit_hours, is_gateway)
                    VALUES (:s, :n, :t, :h, :g) RETURNING course_id"""),
            {"s": subj, "n": num, "t": title, "h": hrs, "g": gateway}
        ).scalar()
        course_ids.append((cid, hrs, gateway))

    # ---- students and their trajectories --------------------------------
    enroll_rows, course_rows, aid_rows = [], [], []
    majors = list(MAJOR_RETENTION.keys())

    for cohort_year in range(FIRST_COHORT_YEAR, LAST_COHORT_YEAR + 1):
        entry_term = terms[(cohort_year, "Fall")]

        for i in range(COHORT_SIZE + TRANSFER_SIZE):
            is_transfer = i >= COHORT_SIZE
            major   = random.choices(majors, weights=MAJOR_WEIGHTS)[0]
            commuter = random.random() < 0.35
            first_gen = random.random() < 0.30
            hs_gpa = round(min(4.0, max(2.0, random.gauss(3.35, 0.42))), 2)

            student_id = conn.execute(
                text("""INSERT INTO students
                        (entry_term_id, entry_type, entry_major, residency,
                         hs_gpa, first_gen)
                        VALUES (:et, :ty, :mj, :res, :gpa, :fg)
                        RETURNING student_id"""),
                {"et": entry_term,
                 "ty": "transfer" if is_transfer else "first-time",
                 "mj": major,
                 "res": "commuter" if commuter else "on-campus",
                 "gpa": hs_gpa,
                 "fg": first_gen}
            ).scalar()

            # transfers arrive with credit already earned
            credits = random.randint(24, 60) if is_transfer else 0
            graduated = False

            # walk forward one academic year at a time
            for year_num in range(1, 7):
                acad_year = cohort_year + year_num - 1
                if acad_year > LAST_TERM_YEAR or graduated:
                    break

                failed_gateway_this_year = False
                aid_this_year = 0

                for season in ["Fall", "Spring"]:
                    if (acad_year, season) not in terms:
                        continue
                    tid = terms[(acad_year, season)]

                    # course load
                    load = random.choices([2, 3, 4, 5], weights=[10, 20, 45, 25])[0]
                    chosen = random.sample(course_ids, load)
                    term_credits = sum(h for _, h, _ in chosen)
                    grade_points, graded = 0, 0

                    for cid, hrs, gateway in chosen:
                        grade = pick_grade(hs_gpa, gateway)
                        course_rows.append(
                            {"s": student_id, "t": tid, "c": cid, "g": grade}
                        )
                        if grade in ("D", "F", "W") and gateway:
                            failed_gateway_this_year = True
                        if grade in ("A", "B", "C", "D", "F"):
                            grade_points += {"A": 4, "B": 3, "C": 2,
                                             "D": 1, "F": 0}[grade]
                            graded += 1

                    term_gpa = round(grade_points / graded, 2) if graded else None
                    credits += sum(h for _, h, g_ in
                                   [(c, h, g) for c, h, g in chosen])
                    if credits >= CREDITS_TO_GRADUATE:
                        graduated = True

                    enroll_rows.append({
                        "s": student_id, "t": tid, "ch": term_credits,
                        "mj": major, "cl": class_level(credits - term_credits),
                        "gpa": term_gpa, "grad": graduated
                    })

                    # financial aid
                    for aid_type in AID_TYPES:
                        if random.random() < 0.28:
                            amt = round(random.uniform(500, 6000), 2)
                            aid_rows.append({"s": student_id, "t": tid,
                                             "a": aid_type, "amt": amt})
                            aid_this_year += amt

                    if graduated:
                        break

                if graduated:
                    break

                # ---- annual departure decision --------------------------
                base = 1.0 - MAJOR_RETENTION[major]
                if commuter:
                    base += COMMUTER_PENALTY
                if first_gen:
                    base += FIRST_GEN_PENALTY
                if hs_gpa < 3.0:
                    base *= LOW_GPA_MULTIPLIER
                if failed_gateway_this_year:
                    base *= GATEWAY_FAIL_MULT
                if aid_this_year >= HIGH_AID_THRESHOLD:
                    base -= HIGH_AID_BONUS

                base *= YEAR_MULTIPLIER.get(year_num, 0.2)
                base = min(0.85, max(0.02, base))

                if random.random() < base:
                    break        # leaves — no rows in later terms

    # ---- bulk insert the child rows -------------------------------------
    # executemany: one round trip per batch instead of per row
    conn.execute(
        text("""INSERT INTO enrollments
                (student_id, term_id, credit_hours, major, class_level,
                 term_gpa, graduated)
                VALUES (:s, :t, :ch, :mj, :cl, :gpa, :grad)"""),
        enroll_rows
    )
    conn.execute(
        text("""INSERT INTO course_enrollments
                (student_id, term_id, course_id, grade)
                VALUES (:s, :t, :c, :g)"""),
        course_rows
    )
    conn.execute(
        text("""INSERT INTO financial_aid
                (student_id, term_id, aid_type, amount)
                VALUES (:s, :t, :a, :amt)"""),
        aid_rows
    )

print(f"enrollments:        {len(enroll_rows):,}")
print(f"course enrollments: {len(course_rows):,}")
print(f"aid records:        {len(aid_rows):,}")