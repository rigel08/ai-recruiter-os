from app.services.skills import skills_in, terms_from_input


def names(terms):
    return [term.name for term in terms]


def test_java_does_not_match_inside_javascript():
    assert names(skills_in("Frontend work in JavaScript and TypeScript")) == ["JavaScript", "TypeScript"]


def test_symbols_in_skill_names_match_literally():
    found = names(skills_in("Wrote services in C++, C# and Node.js on ASP.NET"))
    assert {"C++", "C#", "Node.js", ".NET"} <= set(found)


def test_aliases_map_to_one_skill():
    assert names(skills_in("Used Postgres and ReactJS")) == ["React", "PostgreSQL"]


def test_everyday_words_are_not_skills():
    text = "Eager to excel at work, a swift learner who gets the rest done"
    assert names(skills_in(text)) == []


def test_capitalised_skill_still_matches():
    assert "Excel" in names(skills_in("Advanced Excel and Power BI dashboards"))


def test_multi_word_skills_allow_any_spacing():
    assert "Power BI" in names(skills_in("Power\n BI reports"))


def test_typed_terms_use_vocabulary_and_keep_custom_ones():
    terms = terms_from_input("postgres, Kafka Streams; python\nPYTHON, ")
    assert names(terms) == ["PostgreSQL", "Kafka Streams", "Python"]
    assert terms[1].found_in("Built pipelines with kafka streams")
    assert not terms[1].found_in("Read Kafka")
