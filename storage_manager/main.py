import page
import dll_loader
import pickle
import os
import multiprocessing
import threading
from abc import ABC
from Queryparser.breaker import *

class StorageManager(ABC):
    num_operations=0
    def __init__(self):
        self.dir=os.path()
    
    @staticmethod
    def _start_operation(self):
        self.num_operations+=1
    @staticmethod 
    def _end_operation(self):
        self.num_operations-=1