import sugartensor as tf
from abc import ABCMeta, abstractclassmethod

__author__ = 'george.val.stoyan0v@gmail.com'


class DataLoader(object):
    _CSV_DELIM = ","
    _DEFAULT_SKIP_HEADER_LINES = 0
    _name = "data_loader"
    _num_threads = 1  # 32
    _batch_size = 3  # 64
    _min_after_dequeue = _batch_size * _num_threads
    _capacity = 10  # _min_after_dequeue + (_num_threads + 16) * _batch_size  # as recommended in tf tutorial

    def __init__(self, file_names, record_defaults, field_delim, skip_header_lines=_DEFAULT_SKIP_HEADER_LINES,
                 num_threads=_num_threads, batch_size=_batch_size, min_after_dequeue=_min_after_dequeue,
                 capacity=_capacity, name=_name):
        self.__file_names = file_names
        self.__field_delim = field_delim
        self.__record_defaults = record_defaults
        self.__skip_header_lines = skip_header_lines

        self.num_threads = num_threads
        self._batch_size = batch_size
        self._min_after_dequeue = min_after_dequeue
        self._capacity = capacity
        self._name = name

        self.shuffle_queue = tf.RandomShuffleQueue(capacity=self._capacity, min_after_dequeue=self._min_after_dequeue,
                                              dtypes=[tf.string, tf.int32], shapes=None)

    def get_data(self):
        return self.__load_batch(self.__file_names, record_defaults=self.__record_defaults,
                                 field_delim=self.__field_delim, skip_header_lines=self.__skip_header_lines,
                                 num_epochs=None, shuffle=True)

    def __load_batch(self, file_names, record_defaults, field_delim=_CSV_DELIM, skip_header_lines=0,
                     num_epochs=None, shuffle=True):
        filename_queue = tf.train.string_input_producer(
            file_names, num_epochs=num_epochs, shuffle=shuffle
        )

        example, label = self._read_file(filename_queue, record_defaults, field_delim, skip_header_lines)

        # convert to tensor of strings
        split_example = tf.string_split([example], " ")

        # determine lengths of sequences
        line_number = split_example.indices[:, 0]
        line_position = split_example.indices[:, 1]
        lengths = (tf.segment_max(data=line_position,
                                  segment_ids=line_number) + 1).sg_cast(dtype=tf.int32)

        # convert sparse to dense
        dense_example = tf.sparse_tensor_to_dense(split_example, default_value="")

        # get the enqueue op to pass to a coordintor to be run
        self.enqueue_op = self.shuffle_queue.enqueue([dense_example, label])
        dense_example, label = self.shuffle_queue.dequeue()

        # reshape from <unknown> shape into proper form after dequeue from random shuffle queue
        # this is needed so next queue can automatically infer the shape properly
        dense_example = dense_example[0].sg_reshape(shape=[1, -1])
        label = label.sg_reshape(shape=[1])

        _, (padded_examples, label_examples) = tf.contrib.training.bucket_by_sequence_length(lengths,
                                                                                             [dense_example, label],
                                                                                             batch_size=self._batch_size,
                                                                                             bucket_boundaries=[3],
                                                                                             dynamic_pad=True,
                                                                                             capacity=self._capacity,
                                                                                             num_threads=self._num_threads)

        return padded_examples, label_examples

    def _read_file(self, filename_queue, record_defaults, field_delim=_CSV_DELIM,
                   skip_header_lines=_DEFAULT_SKIP_HEADER_LINES):
        """
        Each class should implement this depending on the file format they want to read, default is csv
        :param filename_queue: 
        :return: 
        """

        reader = tf.TextLineReader(skip_header_lines=skip_header_lines)
        key, value = reader.read(filename_queue)

        _, example, label = tf.decode_csv(value, record_defaults, field_delim)

        return example, label

    @abstractclassmethod
    def _preprocess_example(self, example):
        """
        Applies preprocessing where to the examples
        :param example: an example to preprocess
        :return: the preprocessed example
        """

        return example