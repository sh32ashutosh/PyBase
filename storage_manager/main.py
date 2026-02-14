import page
import dll_loader
import pickle
import os
import multiprocessing
import threading
from abc import ABC


class StorageManager(ABC):
    num_operations=0
    def __init__(self):
        self.dir=None
        self.num_operations=0
    
    @staticmethod
    def _start_operation(self):

        self.num_operations+=1
    @staticmethod 
    def _end_operation(self):
        self.num_operations-=1

if __name__=="__main__":
    sm=StorageManager()
    sm._start_operation()
    print(sm.num_operations)