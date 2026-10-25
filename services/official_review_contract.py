"""Shared structural contract; does not judge factual truth."""
VERDICTS = frozenset({'confirmed', 'contradicted', 'insufficient_evidence', 'out_of_scope'})


def validate_claim_verdicts(value, claims):
    if not isinstance(value, dict) or not isinstance(claims, list) or not claims:
        raise ValueError('Review and nonempty input claims required')
    expected = [c.get('id') for c in claims if isinstance(c, dict)]
    if len(expected) != len(claims) or any(not isinstance(x, str) or not x for x in expected) or len(set(expected)) != len(expected):
        raise ValueError('Input Claim IDs must be nonempty and unique')
    reviewed = value.get('claims')
    if not isinstance(reviewed, list) or len(reviewed) != len(expected) or any(not isinstance(c, dict) for c in reviewed):
        raise ValueError('Official review must cover each claim exactly once')
    ids = [c.get('id') for c in reviewed]
    if any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ValueError('Official review must cover each claim exactly once')
    for claim in reviewed:
        if not isinstance(claim.get('verdict'), str) or claim['verdict'] not in VERDICTS:
            raise ValueError('Invalid official verdict')
        if claim['verdict'] == 'confirmed' and (not isinstance(claim.get('evidence'), str) or not claim['evidence'].strip()):
            raise ValueError('Confirmation requires evidence')
    return reviewed
