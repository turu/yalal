![](https://github.com/turu/yalal/workflows/Continuous%20Integration/badge.svg)

Table of Contents
=================

   * [About YALAL](#about-yalal-v030)
   * [What's the point](#whats-the-point)
   * [What's inside](#whats-inside)
      * [Stream processing](#stream-processing)
         * [Item filters](#item-filters)
         * [Item Counters](#item-counters)
         * [Stream moments](#stream-moments)
   * [Should I use these implementations in production](#should-i-use-these-implementations-in-production)
   * [How to build & test](#how-to-build--test)

# About YALAL v0.3.0
_**Y**et **A**nother **L**ame **A**lgorithm **L**ibrary_ 
is an ever growing collection of algorithms and data structures 
used in **machine learning** and large scale **data processing**, 
implemented from scratch for fun and (no) profit. Also, it's a wordplay on
https://www.urbandictionary.com/define.php?term=yalla, which is very adequate
considering what's in the next section...

# What's the point
As any field progresses, new tools and libraries are created 
to make our lives easier. They help us turn ideas into working 
products faster and with better quality. They achieve this thanks 
to an ever increasing levels of abstraction. Unfortunately high 
level of abstraction comes with a cost. It becomes easy to miss 
or loose grasp of the inner workings of particular tools, 
models and algorithms.

This repository is an attempt to keep us sharp and our feet 
firmly on the ground - to consolidate understanding of 
the intuition behind these algorithms and encode it in the form 
of plain source code with minimal dependencies. The code is plain and simple 
relative to the abstraction level of a particular algorithm/data structure.
This means that it does indeed use varying levels of external dependencies to
avoid writing _everything_ from scratch, which would add noise and make some
implementations infeasible. The main guiding principle, when choosing
what to delegate to a dependency and what to implement, is whether it will 
help understand intuitions behind every implemented solution.

**To implement is to understand.**

# What's inside
Algorithms and data structures implemented in YALAL, are divided into packages and submodules
aligned with their real life domains and applications. Each comes with:
  * a (hopefully) clear and informative implementation
  * short documentation
  * small suite of sanity tests and
  * (optionally) an accompanying Jupyter notebook

Currently the following topics are covered:
## Stream processing
### Item filters
Algorithms to test for item uniqueness ("have I seen this item before?") in an infinite stream of data:
1. Bloom Filter
2. Cuckoo Filter
### Item counters
Algorithms to count the number of distinct, unique elements in an infinite stream of data:
1. HyperLogLog
### Stream moments
Algorithms to compute mean, variance & standard deviation, skewness and kurtosis of infinite streams of data:
1. Welford-Knuth-Pebay one-pass, parallel, statistical moments

# Should I use these implementations in production
![N|Solid](https://i.kym-cdn.com/entries/icons/mobile/000/005/180/YaoMingMeme.jpg)

**If you like to see the world burn, then yes. Otherwise, caution is advised.**

The source code of algorithms and data structures in this repository is not optimized. 
It is intentionally as pure and pseudo-code-like as possible. It may also ignore certain corner-cases for the sake of
simplicity. The primary purpose of this library is to serve as a repository of reference implementations, to aid and 
maintain understanding.  

# How to build & test
1. (Re)create environment: ```source recreate_environment.sh```
2. Build, install & test: ```python setup.py install test```
