#!/usr/bin/env python
# coding:utf-8
import unittest

import os, sys
sys.path.insert(1, os.path.join(os.path.dirname(__file__), os.pardir))
from grade import PayrollGradeLogic


class TestStaffOrg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print "a"