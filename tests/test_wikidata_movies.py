from backend.importers.wikidata_movies import normalize_results


def binding(qid, title, release, sitelinks='10'):
    return {
        'film': {'value': f'http://www.wikidata.org/entity/{qid}'},
        'filmLabel': {'value': title},
        'description': {'value': 'short factual film description'},
        'releaseDate': {'value': release},
        'director': {'value': 'Director'},
        'actor': {'value': 'Actor'},
        'genre': {'value': 'Drama'},
        'country': {'value': 'Country'},
        'sitelinks': {'value': sitelinks},
    }


def test_selects_at_most_two_per_month_and_assigns_year_ranks():
    rows = [binding(f'Q{i}', f'Film {i}', f'1960-01-{i:02d}', str(20 - i)) for i in range(1, 5)]
    rows.append(binding('Q5', 'February Film', '1960-02-01'))
    selected = normalize_results({'results': {'bindings': rows}}, 1960, 2)
    assert len(selected) == 3
    assert [item['title'] for item in selected] == ['Film 1', 'Film 2', 'February Film']
    assert [item['rank'] for item in selected] == [1, 2, 3]


def test_duplicate_qid_keeps_earliest_release():
    rows = [binding('Q1', 'Film', '1960-03-20'), binding('Q1', 'Film', '1960-03-01')]
    selected = normalize_results({'results': {'bindings': rows}}, 1960, 2)
    assert len(selected) == 1
    assert selected[0]['release_date'] == '1960-03-01'


def test_invalid_or_wrong_year_dates_are_skipped():
    rows = [binding('Q1', 'Film', '1961-01-01'), binding('Q2', 'Film', 'not-a-date')]
    assert normalize_results({'results': {'bindings': rows}}, 1960, 2) == []
