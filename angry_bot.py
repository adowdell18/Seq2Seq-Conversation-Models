# -*- coding: utf-8 -*-
"""Angry_Bot.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1GY8ofD8UtujuPqOOlUqXRW60Tchl3Id5
"""

"""The current file is a modification of the following code sources""
/**************************************************
* Title: Chatbot Startkit in TensorFlow 1.4
* Author: Anacin, Luka
* Date: 2017
* Code version: 1.4
* Availability: https://github.com/lucko515/chatbot-startkit
***************************************************/

/**************************************************
* Title: seq2seq-chatbot
* Author: Sanders, Avi
* Date: 2018
* Code version: n/a
* Availability: https://github.com/AbrahamSanders/seq2seq-chatbot
***************************************************/

#import tensorflow as tf
from tensorflow.python.layers.core import Dense

#assert tf.__version__ == '1.4.0'

import tensorflow as tf
import numpy as np
#import config
#from model_utils import Chatbot
#from cornell_data_utils import *
from tqdm import tqdm
import codecs
import math
import gensim
from nltk.translate.bleu_score import sentence_bleu

import re
import numpy as np
import time
#import config
from collections import Counter
device_name = tf.test.gpu_device_name()
print(device_name )

# Load Google's pre-trained Word2Vec model.
#model = gensim.models.Word2Vec.load_word2vec_format('./model/GoogleNews-vectors-negative300.bin', binary=True)

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def grap_inputs():
    '''
		This function is used to define all tensorflow graph placeholders (inputs to the TF graph)

		Inputs: None

		Outputs:
			inputs - questions in the case of a Chatbot with dimensions of None, None = batch_size, questions_length
			targets - answers in the case of a Chatbot with dimensions of None, None = batch_size, answers_length
			keep_probs - probabilities used in dropout layer

			encoder_seq_len -  vector which is used to define lenghts of each sample in the inputs to the model
			decoder_seq_len - vector which is used to define lengths of each sample in the targets to the model
			max_seq_len - target sample with the most words in it

    '''
    inputs = tf.placeholder(tf.int32, [None, None], name='inputs')
    targets = tf.placeholder(tf.int32, [None, None], name='targets')
    keep_probs = tf.placeholder(tf.float32, name='dropout_rate')
    
    encoder_seq_len = tf.placeholder(tf.int32, (None, ), name='encoder_seq_len')
    decoder_seq_len = tf.placeholder(tf.int32, (None, ), name='decoder_seq_len')
    
    #encoder_seq_len = tf.placeholder(tf.int32, ([]), name='encoder_seq_len')
    #decoder_seq_len = tf.placeholder(tf.int32, ([]), name='decoder_seq_len')
    
    max_seq_len = tf.reduce_max(decoder_seq_len, name='max_seq_len')
    
    return inputs, targets, keep_probs, encoder_seq_len, decoder_seq_len, max_seq_len

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018

def encoders(inputs, rnn_size, number_of_layers, encoder_seq_len, keep_probs, encoder_embed_size, encoder_vocab_size):

	
		#Used to define encoder of the seq2seq model (The encoder is made of simple dynamic RNN network).

		#Inputs:
			#inputs -
			#rnn_siz - number of units in the RNN layer
			#number_of_layer - number of RNN layers that the model uses
			#encoder_seq_len - vector of lengths (got from placeholder)
			#keep_probs - dropout rate
			#encoder_embed_size - size of embedding vector for encoder part
			#encoder_vocab_size - number of different words that the model uses in a vocabulary
		
		#Outputs:
			#encoder_outputs -
			#encoder_states - internal states from the RNN layer(s)
    
    
    
    encoder_cell = tf.contrib.rnn.MultiRNNCell([cell(rnn_size, keep_probs) for _ in range(number_of_layers)])
     
    encoder_embedings = tf.contrib.layers.embed_sequence(inputs, encoder_vocab_size, encoder_embed_size) #used to create embeding layer for the encoder
    
    encoder_outputs, encoder_states = tf.nn.dynamic_rnn(encoder_cell, 
                                                        encoder_embedings, 
                                                        encoder_seq_len, 
                                                        dtype=tf.float32)
    
    return encoder_outputs, encoder_states
#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018

def cell(units, rate):
        layer = tf.contrib.rnn.BasicLSTMCell(units)
        return tf.contrib.rnn.DropoutWrapper(layer, rate)
#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018

def decoder_inputs_preprocessing(targets, word_to_id, batch_size):
	
		#Helper function used to prepare decoder inputs

		#Inputs:
			#targets -
			#word_to_id - dictionery that the model uses to map each word to it's int representation
			#batch_size - number of samples that we put through the model at onces

		#Outputs:
			#preprocessed version of decoder inputs

    endings = tf.strided_slice(targets, [0, 0], [batch_size, -1], [1, 1]) #This line is used to REMOVE last member of each sample in the decoder_inputs batch
    return tf.concat([tf.fill([batch_size, 1], word_to_id['<GO>']), endings], 1) #returning line and in this line we concat '<GO>' tag at the beginning of each sample in the batch

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def decoders(decoder_inputs, enc_states, dec_cell, decoder_embed_size, vocab_size,
            dec_seq_len, max_seq_len, word_to_id, batch_size):

	
		
		#The decoder core function.
    #Following comments Adapted from: https://github.com/AbrahamSanders/seq2seq-chatbot and Based on https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
		#Inputs:
			#decoder_inputs -
			#enc_states - states created by the encoder part of the seq2seq network
			#dec_cell - RNN cell used in the decoder RNN (can be attention cell as well)
			#decoder_embed_size - vector size of the decoder embedding layer
			#vocab_size - number of different words used in the decoder part
			#dec_seq_len - vector of lengths for the decoder, obtained from the placeholder
			#max_seq_len - sample with max number of words (got from placeholder)
			#word_to_id - python dict used to encode each word to it's int representation
			#batch_size - number of samples that we put through the model at onces

		#Outputs:
			#train_dec_outputs -
			#inference_dec_output - Inportant for testing and production use!
	
    
    #Defining embedding layer for the Decoder
    embed_layer = tf.Variable(tf.random_uniform([vocab_size, decoder_embed_size]))
    embedings = tf.nn.embedding_lookup(embed_layer, decoder_inputs) 
    
    #Creating Dense (Fully Connected) layer at the end of the Decoder -  used for generating probabilities for each word in the vocabulary
    output_layer = Dense(vocab_size, kernel_initializer=tf.truncated_normal_initializer(0.0, 0.1))
    

    with tf.variable_scope('decoder'):
        #Training helper used only to read inputs in the TRAINING stage
        train_helper = tf.contrib.seq2seq.TrainingHelper(embedings, 
                                                          dec_seq_len)
        
        #Defining decoder - You can change with BeamSearchDecoder, just beam size
        train_decoder = tf.contrib.seq2seq.BasicDecoder(dec_cell, 
                                                        train_helper, 
                                                        enc_states, 
                                                        output_layer)
        
        #Finishing the training decoder
        train_dec_outputs, _, _ = tf.contrib.seq2seq.dynamic_decode(train_decoder, 
                                                                    impute_finished=True, 
                                                                    maximum_iterations=max_seq_len)
        
    with tf.variable_scope('decoder', reuse=True): #we use REUSE option in this scope because we want to get same params learned in the previouse 'decoder' scope
        #getting vector of the '<GO>' tags in the int representation
        starting_id_vec = tf.tile(tf.constant([word_to_id['<GO>']], dtype=tf.int32), [batch_size], name='starting_id_vec')
        
        #using basic greedy to get next word in the inference time (based only on probs)
        inference_helper = tf.contrib.seq2seq.GreedyEmbeddingHelper(embed_layer, 
                                                                    starting_id_vec, 
                                                                    word_to_id['<EOS>'])
        
        #Defining decoder - for inference time
        inference_decoder = tf.contrib.seq2seq.BasicDecoder(dec_cell,
                                                            inference_helper, 
                                                            enc_states, 
                                                            output_layer)
        
        
        inference_dec_output, _, _ = tf.contrib.seq2seq.dynamic_decode(inference_decoder, 
                                                                       impute_finished=True, 
                                                                       maximum_iterations=max_seq_len)
        
    return train_dec_outputs, inference_dec_output


#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def attention_mech(rnn_size, keep_probs, encoder_outputs, encoder_states, encoder_seq_len, batch_size):
    
		#The helper function used to create attention mechanism in TF 1.4

		#Inputs:
			#rnn_size - number of units in the RNN layer
			#keep_probs -  dropout rate
			#encoder_outputs - ouputs got from the encoder part
			#encoder_states - states trained/got from encoder
			#encoder_seq_len - 
			#batch_size - 

		#Outputs:
			#dec_cell - attention based decoder cell
			#enc_state_new -new encoder stated with attention for the decoder


    #using internal function to easier create RNN cell
    def cell(units, probs):
        layer = tf.contrib.rnn.BasicLSTMCell(units)
        return tf.contrib.rnn.DropoutWrapper(layer, probs)
    
    #defining rnn_cell
    decoder_cell = cell(rnn_size, keep_probs)
    
    #using helper function from seq2seq sub_lib for Bahdanau attention
    attention_mechanism = tf.contrib.seq2seq.BahdanauAttention(rnn_size, 
                                                               encoder_outputs, 
                                                               encoder_seq_len)
    
    #finishin attention with the attention holder - Attention Wrapper
    dec_cell = tf.contrib.seq2seq.AttentionWrapper(decoder_cell, 
                                                   attention_mechanism, 
                                                   rnn_size/2)
    
    #Here we are usingg zero_state of the LSTM (in this case) decoder cell, and feed the value of the last encoder_state to it
    attention_zero = dec_cell.zero_state(batch_size=batch_size, dtype=tf.float32)
    enc_state_new = attention_zero.clone(cell_state=encoder_states[-1])
    
    return dec_cell, enc_state_new

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def opt_loss(outputs, targets, dec_seq_len, max_seq_len, learning_rate, clip_rate):
    
		#Function used to define optimizer and loss function

		#Inputs:
			#outputs - outputs got from decoder part of the network
			#targets - expected outputs/ labels
			#dec_seq_len -
			#max_seq_len - 
			#learning_rate - small nubmer used to decrease value of gradients used to update our network
			#clip_rate - tolerance boundries for clipping gradients

		#Outputs:
			#loss -
			#trained_opt - optimizer with clipped gradients
   
    logits = tf.identity(outputs.rnn_output)
    
    mask_weigts = tf.sequence_mask(dec_seq_len, max_seq_len, dtype=tf.float32)
    
    with tf.variable_scope('opt_loss'):
        #using sequence_loss to optimize the seq2seq model
        loss = tf.contrib.seq2seq.sequence_loss(logits, 
                                                targets, 
                                                mask_weigts)
        
        #Define optimizer
        opt = tf.train.AdamOptimizer(learning_rate)

        #Next 3 lines used to clip gradients {Prevent gradient explosion problem}
        gradients = tf.gradients(loss, tf.trainable_variables())
        clipped_grads, _ = tf.clip_by_global_norm(gradients, clip_rate)
        traiend_opt = opt.apply_gradients(zip(clipped_grads, tf.trainable_variables()))
        
    return loss, traiend_opt

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
class Chatbot(object):
    
    def __init__(self, learning_rate, batch_size, enc_embed_size, dec_embed_size, rnn_size, 
                 number_of_layers, vocab_size, word_to_id, clip_rate):
        
        tf.reset_default_graph()
        
        self.inputs, self.targets, self.keep_probs, self.encoder_seq_len, self.decoder_seq_len, max_seq_len = grap_inputs()
        
        
        enc_outputs, enc_states = encoders(self.inputs, 
                                          rnn_size,
                                          number_of_layers, 
                                          self.encoder_seq_len, 
                                          self.keep_probs, 
                                          enc_embed_size, 
                                          vocab_size)
        
        dec_inputs = decoder_inputs_preprocessing(self.targets, 
                                                  word_to_id, 
                                                  batch_size)
        
        
        decoder_cell, encoder_states_new = attention_mech(rnn_size, 
                                                          self.keep_probs, 
                                                          enc_outputs, 
                                                          enc_states, 
                                                          self.encoder_seq_len, 
                                                          batch_size)
        
        train_outputs, inference_output = decoders(dec_inputs, 
                                                  encoder_states_new, 
                                                  decoder_cell,
                                                  dec_embed_size, 
                                                  vocab_size, 
                                                  self.decoder_seq_len, 
                                                  max_seq_len, 
                                                  word_to_id, 
                                                  batch_size)
        
        self.predictions  = tf.identity(inference_output.sample_id, name='preds')
        
        self.loss, self.opt = opt_loss(train_outputs, 
                                       self.targets, 
                                       self.decoder_seq_len, 
                                       max_seq_len, 
                                       learning_rate, 
                                       clip_rate)

from google.colab import drive
drive.mount('/content/gdrive', force_remount=True)

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018

VOCAB_THRESHOLD = 5


BUCKETS = [ (50, 30)] #First try buckets you can tweak these

EPOCHS = 100

BATCH_SIZE = 64

RNN_SIZE = 512

NUM_LAYERS = 3

ENCODING_EMBED_SIZE = 512
DECODING_EMBED_SIZE = 512

LEARNING_RATE = 0.0001
LEARNING_RATE_DECAY = 0.9 #nisam siguran da cu ovo koristiti
MIN_LEARNING_RATE = 0.0001

KEEP_PROBS = 0.5

CLIP_RATE = 4

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def get_conversations():
	
		
		#Function made ONLY for Cornell dataset to extract conversations from the raw file.

	
	conversations = []
	with open('raw_cornell_data/movie_conversations.txt', 'r') as f:
		for line in f.readlines():
			
			conversation = line.split(' +++$+++ ')[-1]
			conversation = conversation.replace("'", "")
			conversation = conversation[1:-2]
			conversation = conversation.split(", ")
			conversations.append(conversation)

	return conversations


#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def get_movie_lines():

	
		#The helper function used to extract movie_lines from the Cornell dataset

	
	sentences = {}
	with open('raw_cornell_data/movie_lines.txt', 'r') as f:
		for line in f.readlines():
			sentences[line.split(' +++$+++ ')[0]] = line.split(' +++$+++ ')[-1].replace('\n', "")

	return sentences

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def questions_vs_answers(convs, lines):
	

		#Save to the file questions and answers extracted from the raw files. VERSION 1

	

	for i in range(len(convs)):
		conversation = convs[i]
		if len(conversation) % 2 == 0:
			for line in range(len(conversation)):
				if line % 2 == 0:
					with open('movie_questions.txt', 'a') as f:
						f.write(lines[conversation[line]] + "\n")
				else:
					with open('movie_answers.txt', 'a') as f:
						f.write(lines[conversation[line]] + "\n")

def questions_vs_answers_v2(convs, lines):


		#Save to the file questions and answers extracted from the raw files. VERSION 2


	for i in range(len(convs)):
		conversation = convs[i]
		for line in range(len(conversation) - 1):

			with open('movie_questions_2.txt', 'a') as f:
				f.write(lines[conversation[line]] + "\n")
			with open('movie_answers_2.txt', 'a') as f:
				f.write(lines[conversation[line + 1]] + "\n")

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def cornell_tokenizer(text):
	
		#Basic, starting tokenizer used for sentence preprocessing.

	
	text = re.sub(r"\'m", " am", text)
	text = re.sub(r"\'s", " is", text)
	text = re.sub(r"\'re", " are", text)
	text = re.sub(r"\'ll", " will", text)
	text = re.sub(r"\'d", " would", text)
	text = re.sub(r"won't", "will not", text)
	text = re.sub(r"can't", "cannot", text)
	text = re.sub(r"\.", " . ", text)
	text = re.sub(r"\?", " ? ", text)
	text = re.sub(r"!", " ! ", text)
	text = re.sub(r"/", " / ", text)
	text = re.sub(r",", " , ", text)
	text = re.sub(r'"', ' " ', text)
	text = re.sub(r"-", " - ", text)

	text = re.sub(r"[-<>{}+=|?'()\:@]", "", text)
	return text.replace('\n', '')

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def clean_data():
	
		#Raw data clearner.
	
	cleaned_questions = []
	cleaned_answers = []
  #cnt=0
	with codecs.open('gdrive/My Drive/movie_questions_2.txt', 'r', encoding = 'utf-8', errors = 'ignore') as f:
    #str = unicode(str, errors='ignore')
    #a.encode('utf-8').strip()
		lines = f.readlines()
    
		for line in lines:
			cleaned_questions.append(cornell_tokenizer(line))

	with codecs.open('gdrive/My Drive/movie_answers_2.txt', 'r', encoding = 'utf-8', errors = 'ignore') as f:
		lines = f.readlines()
 
		for line in lines:
     
			cleaned_answers.append(cornell_tokenizer(line))
      
	return cleaned_questions, cleaned_answers

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def clean_data_2():
	
		#Raw data clearner.
	
	cleaned_questions = []
	cleaned_answers = []
  #cnt=0
	with codecs.open('angry_bot_questions.txt', 'r', encoding = 'utf-8', errors = 'ignore') as f:
    #str = unicode(str, errors='ignore')
    #a.encode('utf-8').strip()
		lines = f.readlines()
    
		for line in lines:
			cleaned_questions.append(cornell_tokenizer(line))

	with codecs.open('angry_bot_answers.txt', 'r', encoding = 'utf-8', errors = 'ignore') as f:
		lines = f.readlines()
 
		for line in lines:
     
			cleaned_answers.append(cornell_tokenizer(line))
      
	return cleaned_questions, cleaned_answers

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def create_vocab(questions, answers):

	
		
		#This function is used to create vocabulary, word_to_id and id_to_word dicts from cleaned data (got from the last question).


	assert len(questions) == len(answers)
	vocab = []
	for i in range(len(questions)):
		words = questions[i].split()
		for word in words:
			vocab.append(word)

		words = answers[i].split()
		for word in words:
			vocab.append(word)


	vocab = Counter(vocab)
	new_vocab = []
	for key in vocab.keys():
		if vocab[key] >= VOCAB_THRESHOLD:
			new_vocab.append(key)

	new_vocab = ['<PAD>', '<GO>', '<UNK>', '<EOS>'] + new_vocab

	word_to_id = {word:i for i, word in enumerate(new_vocab)}
	id_to_word = {i:word for i, word in enumerate(new_vocab)}

	return new_vocab, word_to_id, id_to_word

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def encoder(data, word_to_id, targets=False):
	
		#Using word_to_id dictionery to map each word in the sample to it's own int representation

	
	encoded_data = []

	for i in range(len(data)):

		encoded_line = []
		words = data[i].split()
		for word in words:

			if word not in word_to_id.keys():
				encoded_line.append(word_to_id['<UNK>'])
			else:
				encoded_line.append(word_to_id[word])

		if targets:
			encoded_line.append(word_to_id['<EOS>'])

		encoded_data.append(encoded_line)

          
	return np.array(encoded_data)

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def pad_data(data, word_to_id, max_len, target=False):
		#If the sentence is shorter then wanted length, pad it to that length

	if target:
		return data + [word_to_id['<PAD>']] * (max_len - len(data))
	else:
		return [word_to_id['<PAD>']] * (max_len - len(data)) + data

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def bucket_data(questions, answers, word_to_id):

	
		#If you prefere bucketing version of the padding, use this function to create buckets of your data.

	assert len(questions) == len(answers)

	bucketed_data = []
	already_added = []
	for bucket in BUCKETS:
		data_for_bucket = []
		encoder_max = bucket[0]
		decoder_max = bucket[1]
		for i in range(len(questions)):
			if len(questions[i]) <= encoder_max and len(answers[i]) <= decoder_max:
				if i not in already_added:
					data_for_bucket.append((pad_data(questions[i], word_to_id, encoder_max), pad_data(answers[i], word_to_id, decoder_max, True)))
					already_added.append(i)

		bucketed_data.append(data_for_bucket)
    #print(bucketed_data)
    #print(bucketed_data)

	return bucketed_data

"""### Define get_accuracy helper function to check accuracy of the sequence data"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def get_accuracy(target, logits):
    """
    Calculate accuracy
    """
    max_seq = max(target.shape[1], logits.shape[1])
    if max_seq - target.shape[1]:
        target = np.pad(
            target,
            [(0,0),(0,max_seq - target.shape[1])],
            'constant')
    if max_seq - logits.shape[1]:
        logits = np.pad(
            logits,
            [(0,0),(0,max_seq - logits.shape[1])],
            'constant')

    return np.mean(np.equal(target, logits))

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def int2str(strings):
    answer = ''
    for i in strings:
        if id_to_word[i] == 'i':
            token = ' I'
        elif id_to_word[i] == '<EOS>':
            token = '.'
        elif id_to_word[i] == '<OUT>':
            token = 'out'
        else:
            token = ' ' + id_to_word[i]
        answer += token
        if token == '.':
            break
    return answer

"""### Data cleaning"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
cleaned_questions, cleaned_answers = clean_data()
print(cleaned_questions[0:3])
print(cleaned_answers[0:3])

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
cleaned_questions_2, cleaned_answers_2 = clean_data_2()
print(cleaned_questions[0:3])
print(cleaned_answers[0:3])
print(len(cleaned_answers_2))
print(len(cleaned_questions_2))

"""### Creating vocab and necessary dictionaries"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
vocab, word_to_id, id_to_word = create_vocab(cleaned_questions, cleaned_answers)
#print(id_to_word)

"""### Data encoding"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
encoded_questions = encoder(cleaned_questions_2, word_to_id)
print(encoded_questions)

#Adapted from: https://github.com/AbrahamSanders/seq2seq-chatbot and Based on https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
encoded_answers = encoder(cleaned_answers_2, word_to_id, True)
print(encoded_answers)

"""TESTING DECODER"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def convert_string2int(question, word2int):
    question = cornell_tokenizer(question)
    return [word2int.get(word, word2int['<UNK>']) for word in question.split()]
quest = cleaned_questions_2[0]
question = convert_string2int(quest, word_to_id)
print(question)

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
def convert_int2string(answer, int2word):
    #question = cornell_tokenizer(question)
    answer = " ".join([int2word.get(word, '<UNK>') for word in answer])
    return answer
#quest = cleaned_answers[0]
answer = convert_int2string(question, id_to_word)
#question = convert_string2int(quest, word_to_id)
print(answer)
#print(int2word)

"""### Bucketting data"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
print(len(encoded_questions))
print(len(encoded_answers))
bucketed_data = bucket_data(encoded_questions, encoded_answers, word_to_id)

print(bucketed_data[0][0][1])

"""### Creating model object, session and defining model saver"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
model = Chatbot(LEARNING_RATE, 
                BATCH_SIZE, 
                ENCODING_EMBED_SIZE, 
                DECODING_EMBED_SIZE, 
                RNN_SIZE, 
                NUM_LAYERS,
                len(vocab), 
                word_to_id, 
                CLIP_RATE) #4=clip_rate

session = tf.Session()

session.run(tf.global_variables_initializer())

saver = tf.train.Saver(max_to_keep=25)

"""### Entering big buckets, training loop"""

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
import os

check=os.listdir("gdrive/My Drive/checkpoint")
loadID=len(check)-1
print(loadID)
#check_points = listdir("gdrive/My Drive/checkpoint1/epoch{}/chatbot.ckpt".format(loadID))
#checkpt_loadID = len(check_points) - 1
#barbie = os.listdir("gdrive/My Drive/checkpoint1/epoch0/chatbot.ckpt")
#saver.restore(session, barbie)
if(loadID>-1):
  #saver.restore(session, "gdrive/My Drive/checkpoint1/epoch{}/chatbot.ckpt".format(0))
  check=os.listdir("gdrive/My Drive/checkpoint/epoch{}".format(loadID))
  BucketID=((len(check)-1)//3)-1
  if(BucketID>-1):
    saver.restore(session, "gdrive/My Drive/checkpoint/epoch{}/chatbot_{}.ckpt".format(loadID,BucketID))
    BucketID=BucketID+1
  else:
    print("There is no checkpoint")
    loadID=0
    BucketID=0
  #for i in range (0, num_checkpts):
    
 #   saver.restore(session,"gdrive/My Drive/checkpoint1/epoch{}/chatbot_{}.ckpt".format(loadID,i))
  #saver.restore(session, "gdrive/My Drive/checkpoint1/epoch{}/chatbot.ckpt".format(loadID))
else:
  print("There is no checkpoint")
  loadID=0
  BucketID=0
  
  #saver.restore(session, "gdrive/My Drive/checkpoint1/epoch{}/checkpoint".format(loadID)) ### only allowed to restore .ckpt files
print(loadID,BucketID)

#check=os.listdir("gdrive/My Drive/test")
  #print(check)
  #saver.restore(session, "gdrive/My Drive/test/checkpoint")

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
for i in range(0,EPOCHS):
    epoch_accuracy = []
    epoch_loss = []
    for b in range(0,len(bucketed_data)):
        bucket = bucketed_data[b]
        questions_bucket = []
        answers_bucket = []
        bucket_accuracy = []
        bucket_loss = []
        for k in range(len(bucket)):
            questions_bucket.append(np.array(bucket[k][0]))
            answers_bucket.append(np.array(bucket[k][1]))
        #for ii in tqdm(range(len(questions_bucket) //  BATCH_SIZE)):
        Number_of_Loop = len(questions_bucket) / BATCH_SIZE
        Number_of_Loop = math.trunc(Number_of_Loop)
        for ii in tqdm(range(Number_of_Loop)):
            
        #for ii in tqdm(range(len(questions_bucket) //  BATCH_SIZE)):
            
            starting_id = ii * BATCH_SIZE
            
            X_batch = questions_bucket[starting_id:starting_id+BATCH_SIZE]
            y_batch = answers_bucket[starting_id:starting_id+BATCH_SIZE]
            
            feed_dict = {model.inputs:X_batch, 
                         model.targets:y_batch, 
                         model.keep_probs:KEEP_PROBS, 
                         model.decoder_seq_len:[len(y_batch[0])]*BATCH_SIZE,
                         model.encoder_seq_len:[len(X_batch[0])]*BATCH_SIZE}
            
            cost, _, preds = session.run([model.loss, model.opt, model.predictions], feed_dict=feed_dict)
            
            epoch_accuracy.append(get_accuracy(np.array(y_batch), np.array(preds)))
            bucket_accuracy.append(get_accuracy(np.array(y_batch), np.array(preds)))
            
            bucket_loss.append(cost)
            epoch_loss.append(cost)
            #for s in preds:
              #print("Chatbot: ",int2str(s))
        #saver.save(session, "gdrive/My Drive/checkpoint/epoch{}/chatbot_{}.ckpt".format(i,b))    
        print("Bucket {}:".format(b+1), 
              " | Loss: {}".format(np.mean(bucket_loss)), 
              " | Accuracy: {}".format(np.mean(bucket_accuracy)))
    BucketID=0

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
for b in range(len(bucketed_data)):
    bucket = bucketed_data[b]
    print(len(bucket))
    for l  in range (10):
        print(l)
        predicted_question=bucket[l][0]
        question = ''
        for i in predicted_question:
            if id_to_word[i] == 'i':
                token = ' I'
            elif id_to_word[i] == '<EOS>':
                token = '.'
            elif id_to_word[i] == '<OUT>':
                token = 'out'
            else:
                token = ' ' + id_to_word[i]
            question += token
            if token == '.':
                break
        print(question)
        predicted_answer=bucket[l][1]
        answer = ''
        for i in predicted_answer:
            if id_to_word[i] == 'i':
                token = ' I'
            elif id_to_word[i] == '<EOS>':
                token = '.'
            elif id_to_word[i] == '<OUT>':
                token = 'out'
            else:
                token = ' ' + id_to_word[i]
            answer += token
            if token == '.':
                break
        print(answer)

#The following code and comments are provided, sourced, and/or modified from the following repositories from: https://github.com/AbrahamSanders/seq2seq-chatbot; https://github.com/lucko515/chatbot-startkit; Retrieved on 10-04-2018
########## PART 4 - TESTING THE SEQ2SEQ MODEL ##########
 
#print(word_to_id)
#cb = Chatbot()
 
# Loading the weights and Running the session
#checkpoint = "./chatbot_weights.ckpt"
#checkpoint = os.listdir("gdrive/My Drive/checkpoint/epoch0/chatbot.ckpt")
'''
session = tf.InteractiveSession()
session.run(tf.global_variables_initializer())
saver = tf.train.Saver()
#saver.restore(session, checkpoint)
 '''
bleu = []
# Converting the questions from strings to lists of encoding integers
def convert_string2int(question, word2int):
    question = cornell_tokenizer(question)
    return [word2int.get(word, word2int['<UNK>']) for word in question.split()]
 
# Setting up the chat
while(True):
    question = input("You: ")
    query = question
    if question == 'Goodbye':
      break
    inBucket=0
    outBucket=0
    question = convert_string2int(question, word_to_id)
    question = question + [word_to_id['<EOS>']]
    if(len(question)<=10):
        inBucket=10
        outBucket=15
    elif(len(question)<=15):
        inBucket=15
        outBucket=25
    elif(len(question)<=25):
        inBucket=25
        outBucket=45
    elif(len(question)<=45):
        inBucket=45
        outBucket=60
    elif(len(question)<=60):
        inBucket=60
        outBucket=100
    question =  [word_to_id['<PAD>']] * (inBucket - len(question)) + question
    
    #print(question)
    #print(outBucket)
    #print(inBucket)
    #print(BATCH_SIZE)
    #fake_batch = np.zeros((BATCH_SIZE, inBucket))
    #fake_batch[0] = question
    fake_batch=[question]*BATCH_SIZE
    predicted_answer = session.run(model.predictions, {model.inputs: fake_batch, model.keep_probs: 0.5,
                                  model.decoder_seq_len:[outBucket]*BATCH_SIZE,
                                  model.encoder_seq_len:[inBucket]*BATCH_SIZE})
    answer = ''
    #print(predicted_answer)
    for i in predicted_answer[0]:
        if id_to_word[i] == 'i':
            token = ' I'
        elif id_to_word[i] == '<EOS>':
            token = '.'
        elif id_to_word[i] == '<OUT>':
            token = 'out'
        else:
            token = ' ' + id_to_word[i]
        answer += token
        if token == '.':
            break
    print('ChatBot: ' + answer)
    # shorter candidate
  #from nltk.translate.bleu_score import sentence_bleu
    reference_list = query.split(" ")
    candidate_list = answer.split(" ")
    print(reference_list)
    print(candidate_list)
    reference = [reference_list]
    candidate = candidate_list
    score = sentence_bleu(reference, candidate)
    print(score)
