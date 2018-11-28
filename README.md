# Twitter-Parser
Twitter Parser based on Tom Dickinson's algorithm.

### Parser params:
**required params:**
 - filename (name of .csv file to which you save the result; you don't need to type ".csv" in the end)
 - since_date (search since this date)
 - until_date (search until this date)
**additional params:**
 - query (search keyword)
 - lang (search only by this language)

If you want to search by phrase, don't use **query** param. The script will ask you for a key phrase after launch.
If you don't want to specify language, just don't use **lang** param. The parser will search for posts in all languages.

### How to run this parser?
```
python3 twitter.py [filename] [since_date] [until_date] -q [query] -l [language]
```

**Example 1:**
Searching from 20 November 2018 to 25 November 2018 for "hardkiss" in all languages.
```
python3 twitter.py test.csv 2018-11-20 2018-11-25 -q hardkiss
```

**Example 2:**
Searching from 10 November 2018 to 25 November 2018 for "global hack weekend" in only russian language.
```
python3 twitter.py test.csv 2018-11-10 2018-11-25 -l ru
Enter a search query please: global hack weekend
```
