import pandas as pd
import numpy as np
import random
from sklearn.base import is_classifier, is_regressor
from sklearn.tree import _tree
from matplotlib import pyplot as plt
from sklearn import datasets
from sklearn.tree import DecisionTreeClassifier 
from sklearn import tree
from matplotlib import pyplot as plt
from sklearn import datasets
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble._forest import ForestClassifier
import sklearn.ensemble._forest
from joblib import Parallel, delayed
import scipy.stats as st
import collections

def get_intervals(in_data):
    ret = st.norm.interval(0.95, loc=np.mean(in_data), scale=st.sem(in_data))
    return ret

class DecisionTreeClassifier_Modified(DecisionTreeClassifier):

    def calc_confidence_intervals(self, i):
        # print('node',i)
        # print(in_y)
        conf_interval_per_node =  collections.defaultdict(list)
        node_labels = self.get_labels_for_node(i)
        for label in node_labels:
            node_label_rows = self.get_samples_for_node(i,label)
            # print('label',label)
            # print('label_rows',label_rows)
            # print(label)
            # print(np.apply_along_axis(get_intervals, 0, clf.samples[label_rows]))
            # print('----')
            conf_interval_per_node[label] = np.apply_along_axis(get_intervals, 0, node_label_rows)
        # print(conf_interval_per_node)
        return conf_interval_per_node

    def calc_confidence_intervals_all(self):
        self.confidence_intervals_per_node = collections.defaultdict(list)
        for i in range(self.tree_.node_count):
            # print(clf.samples[clf.samples_per_node[i]])
            # print(clf.labels[clf.samples_per_node[i]])
            self.confidence_intervals_per_node[i] = self.calc_confidence_intervals(i)
        return True

    def build_samples_per_node(self,X):
        
        self.samples_per_node = collections.defaultdict(list)
        self.train_paths = self.decision_path(X)
        for d, dec in enumerate(self.train_paths):
            for i in range(self.tree_.node_count):
                if dec.toarray()[0][i] == 1:
                    self.samples_per_node[i].append(d)

    def fit(self, X, y, sample_weight=None, check_input=True):
        ret_val = super().fit(X, y, sample_weight, check_input)
        self.samples = X
        self.labels = y
        self.build_samples_per_node(X)
        self.calc_confidence_intervals_all()
        self.node_feature_id = [
                i if i != _tree.TREE_UNDEFINED else "undefined!" for i in self.tree_.feature
            ]
        return ret_val

    def get_samples_for_node(self,node,label=None):
        #todo check node id 
        if label is None:
            return self.samples[self.samples_per_node[node]]
        else:
            return self.samples[self.samples_per_node[node]][self.get_labels_for_node(node)==label]
    
    def get_labels_for_node(self,node):
        return self.labels[self.samples_per_node[node]]
    
    def get_feat_id_threshold_for_node(self,node):
        return  self.node_feature_id[node], self.tree_.threshold[node]

    def calc_split_feature_z_score(self,in_node,in_feature_value):
        try:
            cur_node_samples = self.get_samples_for_node(in_node)
            cur_node_feature_id, cur_feature_threshold = self.get_feat_id_threshold_for_node(in_node)
            sample_mean = np.mean(cur_node_samples[:,cur_node_feature_id])
            sample_std = np.std(cur_node_samples[:,cur_node_feature_id])
            feature_z_score = (in_feature_value -  sample_mean) / sample_std
            threshold_z_score = (cur_feature_threshold -  sample_mean) / sample_std
            if abs(feature_z_score - threshold_z_score) > 0.75:
                return True
            return False
        except Exception as e:
            raise e

    def split_logic_rnd(self,x,node,node_feature_id,in_rnd_list):
        feature_id = node_feature_id[node]
        feature_threshold = self.tree_.threshold[node]
        return (bool((x[feature_id]<=feature_threshold)) != bool(in_rnd_list[node]==1))
    
    def split_logic_z_score(self,x,node,node_feature_id):
        feature_id = node_feature_id[node]
        return self.calc_split_feature_z_score(node,x[feature_id])
    '''
    A recursive predict fucntion

        Parameters:
            x (array): The samples data for prediction
            node(int): Current node in the tree
            depth(int): Current depth of the tree
            node_feature_id (list): A list of all nodes and the feature used for the split on this node.
            in_alpha (float): The probability of taking the opposite direction of what the node condition indicates.
            in_rnd_list(list): A list for each node indicate if to use the correct of the opposite direction of the node.
            to_print(bool): Use for debugging puroposes - print each step
        Returns:
            predict (np.array): The calcualted prediction for each sample
    '''
    def recurse_predict(self, x, node, depth, node_feature_id, in_alpha, in_rnd_list, to_print):
        try:
            if self.tree_.feature[node] != _tree.TREE_UNDEFINED:
                feature_id = node_feature_id[node]
                feature_threshold = self.tree_.threshold[node]
                if to_print:
                    print('feature_id {}. feature_threshold:{}, feature_value:{},rnd:{}'.format(
                        feature_id,feature_threshold,x[feature_id],in_rnd_list[node]))

                if (bool((x[feature_id]<=feature_threshold)) != bool(in_rnd_list[node]==1)):
                #if (bool(self.split_logic_z_score(x, node, node_feature_id)) != bool(in_rnd_list[node]==1)):
                    if to_print:
                        print('took left node')
                    ret_val = self.recurse_predict(x,self.tree_.children_left[node], depth + 1,node_feature_id,in_alpha,in_rnd_list,to_print)
                else:
                    if to_print:
                        print('took right node')
                    ret_val = self.recurse_predict(x,self.tree_.children_right[node], depth + 1,node_feature_id,in_alpha,in_rnd_list,to_print)
                if (ret_val is not None):
                    return ret_val
            else:
                return(self.tree_.value[node][0]/self.tree_.value[node][0].sum())
        except Exception as e:
            print("Error when calling {} function. e:{}".format("recurse_predict",e))
            raise e

    '''
    A warpper function for the recursive predict fucntion

        Parameters:
            x (array): The samples data for prediction
            in_alpha (float): The probability of taking the opposite direction of what the node condition indicates.
            in_node_feature_id (list): A list of all nodes and the feature used for the split on this node.
            in_node_use_random_arr(list): A list for each node indicate if to use the correct of the opposite direction of the node.
            to_print(bool): Use for debugging puroposes - print each step
        Returns:
            predict (np.array): The calcualted prediction for each sample
    '''
    def predict_proba_one(self,x,in_alpha, in_node_feature_id,in_node_use_random_arr,to_print):
        try:
            return self.recurse_predict(x,0, 1,in_node_feature_id,in_alpha,in_node_use_random_arr, to_print)
        
        except Exception as e:
            print("Error when calling {} function".format("predict_proba_one"))
            raise e
    
    '''
    This function iterate for each sample and calculate the predicted probabilty. For performace issues, before calling the predict_proba_one function, this 
    function calculated for all nodes and all samples the indication of whether using the corerct direction or the opposite direction of the node.

        Parameters:
            x (array): The samples data for prediction
            in_alpha (float): The probability of taking the opposite direction of what the node condition indicates.
            to_print(bool): Use for debugging puroposes - print each step
        Returns:
            predict (np.array): The calcualted prediction for each sample
    '''
    def predict_proba_rnd(self,x,in_alpha, to_print):
        try:
            # list of all nodes and which feature is used for the split on the specific node

            # array which holds for all nodes and all samples the indication of whether using the corerct direction or the opposite direction of the node.
            node_use_random_arr = np.random.choice(a=[False,True],size=(np.shape(x)[0],len(self.node_feature_id)),p=[1-in_alpha,in_alpha])

            # convert all samples data to numeric
            #x = x.apply( pd.to_numeric, errors='coerce' )

            # itereate over the samples and call predict for each sample
            ret_val =[]
            for ind,x_row in enumerate(x):
                if (to_print):
                    print('x_row',x_row)
                ret_val.append(self.predict_proba_one(x_row,in_alpha,self.node_feature_id,node_use_random_arr[ind],to_print))
            return np.array(ret_val)
        except Exception as e:
            print("Error when calling {} function".format("predict_proba_rnd"))
            raise e
    
    '''
    This is an override on the legend function predict_proba, this function call the predict_proba_rnd (which get alpha as input and randomly with the
    probability of alpha decided to use the opposite branch of the node).

        Parameters:
            x (array): The samples data for prediction
            in_alpha (float): The probability of taking the opposite direction of what the node condition indicates.
            in_n (int):  in_n times (e.g. n=100) for each sample and then average the probability vectors to provide a final prediction.
            to_print(bool): Use for debugging puroposes - print each step
        Returns:
            predict (np.array): The calcualted prediction for each sample
    '''
    def predict_proba(self,x,in_alpha=0.1,in_n=50,to_print=False,check_input=False):
        try:
            ret_val = Parallel(n_jobs=12)(delayed(self.predict_proba_rnd)(x,in_alpha,to_print) for ind in range(in_n))
            return np.average(np.array(ret_val),axis=0)
        except Exception as e:
            print("Error when calling {} function".format("predict_proba"))
            raise e
