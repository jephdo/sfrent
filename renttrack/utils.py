import re
from unicodedata import normalize

import pandas as pd
import numpy as np

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim='-'):
    """Generates an slightly worse ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize('NFKD', word)#.encode('ascii', 'ignore').decode()
        if word:
            result.append(word)
    return delim.join(result)


def bootstrap(values, trials=1000):
    replicates = []
    for _ in range(trials):
        replicate = values.sample(frac=1., replace=True).mean()
        replicates.append(replicate)
    return pd.Series(replicates)


def trim_outliers(values, percentile=95):
    values = pd.Series(values)
    if len(values) < 100:
        return values[5:-5]
    assert 0 < percentile < 100
    upper = np.percentile(values, percentile)
    lower = np.percentile(values, 100 - percentile)
    return values[(lower < values) & (values < upper)]


