#
# Copyright 2018 Analytics Zoo Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from bigdl.nn.keras.layer import KerasLayer
from bigdl.nn.layer import Node

from zoo.pipeline.api.keras.utils import *

if sys.version >= '3':
    long = int
    unicode = str


class ZooKerasCreator(JavaValue):
    def jvm_class_constructor(self):
        name = "createZooKeras" + self.__class__.__name__
        print("creating: " + name)
        return name


class ZooKerasLayer(ZooKerasCreator, KerasLayer):
    @classmethod
    def of(cls, jvalue, bigdl_type="float"):
        return KerasLayer(jvalue, bigdl_type)


class KerasNet(ZooKerasLayer):
    def compile(self, optimizer, loss, metrics=None):
        """
        Configure the learning process. It MUST be called before fit or evaluate.

        # Arguments
        optimizer: Optimization method to be used. One can alternatively pass in the corresponding
                   string representation, such as 'sgd'.
        loss: Criterion to be used. One can alternatively pass in the corresponding string
              representation, such as 'mse'.
        metrics: List of validation methods to be used. Default is None if no validation is needed.
                 One can alternatively use ['accuracy'].
        """
        if isinstance(optimizer, six.string_types):
            optimizer = to_bigdl_optim_method(optimizer)
        if isinstance(loss, six.string_types):
            loss = to_bigdl_criterion(loss)
        if callable(loss):
            from zoo.pipeline.api.autograd import CustomLoss
            loss = CustomLoss(loss, self.get_output_shape()[1:])
        if metrics and all(isinstance(metric, six.string_types) for metric in metrics):
            metrics = to_bigdl_metrics(metrics)
        callBigDlFunc(self.bigdl_type, "zooCompile",
                      self.value,
                      optimizer,
                      loss,
                      metrics)

    def set_tensorboard(self, log_dir, app_name):
        """
        Set summary information during the training process for visualization purposes.
        Saved summary can be viewed via TensorBoard.
        In order to take effect, it needs to be called before fit.

        Training summary will be saved to 'log_dir/app_name/train'
        and validation summary (if any) will be saved to 'log_dir/app_name/validation'.

        # Arguments
        log_dir: The base directory path to store training and validation logs.
        app_name: The name of the application.
        """
        callBigDlFunc(self.bigdl_type, "zooSetTensorBoard",
                      self.value,
                      log_dir,
                      app_name)

    def set_checkpoint(self, path, over_write=True):
        """
        Configure checkpoint settings to write snapshots every epoch during the training process.
        In order to take effect, it needs to be called before fit.

        # Arguments
        path: The path to save snapshots. Make sure this path exists beforehand.
        over_write: Whether to overwrite existing snapshots in the given path. Default is True.
        """
        callBigDlFunc(self.bigdl_type, "zooSetCheckpoint",
                      self.value,
                      path,
                      over_write)

    def fit(self, x, y=None, batch_size=32, nb_epoch=10, validation_data=None, distributed=True):
        """
        Train a model for a fixed number of epochs on a dataset.

        # Arguments
        x: Input data. A Numpy array or RDD of Sample or Image DataSet.
        y: Labels. A Numpy array. Default is None if x is already RDD of Sample or Image DataSet.
        batch_size: Number of samples per gradient update.
        nb_epoch: Number of iterations to train.
        validation_data: Tuple (x_val, y_val) where x_val and y_val are both Numpy arrays.
                         Or RDD of Sample. Default is None if no validation is involved.
        distributed: Boolean. Whether to train the model in distributed mode or local mode.
                     Default is True. In local mode, x and y must both be Numpy arrays.
        """
        if distributed:
            if isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
                training_data = to_sample_rdd(x, y)
                if validation_data:
                    validation_data = to_sample_rdd(*validation_data)
            elif (isinstance(x, RDD) or isinstance(x, DataSet)) and not y:
                training_data = x
            else:
                raise TypeError("Unsupported training data type: %s" % type(x))
            callBigDlFunc(self.bigdl_type, "zooFit",
                          self.value,
                          training_data,
                          batch_size,
                          nb_epoch,
                          validation_data)
        else:
            if validation_data:
                val_x = [JTensor.from_ndarray(x) for x in to_list(validation_data[0])]
                val_y = JTensor.from_ndarray(validation_data[1])
            else:
                val_x, val_y = None, None
            callBigDlFunc(self.bigdl_type, "zooFit",
                          self.value,
                          [JTensor.from_ndarray(x) for x in to_list(x)],
                          JTensor.from_ndarray(y),
                          batch_size,
                          nb_epoch,
                          val_x,
                          val_y)

    def evaluate(self, x, y=None, batch_size=32):
        """
        Evaluate a model on a given dataset in distributed mode.

        # Arguments
        x: Input data. A Numpy array or RDD of Sample.
        y: Labels. A Numpy array. Default is None if x is already RDD of Sample.
        batch_size: Number of samples per gradient update.
        """
        if isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
            evaluation_data = to_sample_rdd(x, y)
        elif isinstance(x, RDD) and not y:
            evaluation_data = x
        else:
            raise TypeError("Unsupported evaluation data type: %s" % type(x))
        return callBigDlFunc(self.bigdl_type, "zooEvaluate",
                             self.value,
                             evaluation_data,
                             batch_size)

    def predict(self, x, distributed=True):
        """
        Use a model to do prediction.

        # Arguments
        x: Input data. A Numpy array or RDD of Sample.
        distributed: Boolean. Whether to do prediction in distributed mode or local mode.
                     Default is True. In local mode, x must be a Numpy array.
        """
        if is_distributed:
            if isinstance(x, np.ndarray):
                features = to_sample_rdd(x, np.zeros([x.shape[0]]))
            elif isinstance(x, RDD):
                features = x
            else:
                raise TypeError("Unsupported prediction data type: %s" % type(x))
            return self.predict_distributed(features)
        else:
            if isinstance(x, np.ndarray):
                return self.predict_local(x)
            else:
                raise TypeError("Unsupported prediction data type: %s" % type(x))


class Input(ZooKerasCreator, Node):
    """
    Used to instantiate an input node.

    # Arguments
    shape: A shape tuple, not including batch.
    name: String to set the name of the layer.
          If not specified, its name will by default to be a generated string.

    >>> input = Input(name="input1", shape=(3, 5))
    creating: createZooKerasInput
    """
    def __init__(self, shape=None, name=None, bigdl_type="float"):
        super(Input, self).__init__(None, bigdl_type,
                                    name,
                                    list(shape) if shape else None)


class InputLayer(ZooKerasLayer):
    """
    Used as an entry point into a model.

    # Arguments
    input_shape: A shape tuple, not including batch.
    name: String to set the name of the layer.
          If not specified, its name will by default to be a generated string.

    >>> inputlayer = InputLayer(input_shape=(3, 5), name="input1")
    creating: createZooKerasInputLayer
    """
    def __init__(self, input_shape=None, **kwargs):
        super(InputLayer, self).__init__(None,
                                         list(input_shape) if input_shape else None,
                                         **kwargs)


class Merge(ZooKerasLayer):
    """
    Used to merge a list of inputs into a single output, following some merge mode.
    Merge must have at least two input layers.

    When using this layer as the first layer in a model, you need to provide the argument
    input_shape for input layers (a list of shape tuples, does not include the batch dimension).

    # Arguments
    layers: A list of layer instances. Must be more than one layer.
    mode: Merge mode. String, must be one of: 'sum', 'mul', 'concat', 'ave', 'cos',
          'dot', 'max', 'sub', 'div', 'min'. Default is 'sum'.
    concat_axis: Int, axis to use when concatenating layers.
                 Only specify this when merge mode is 'concat'.
                 Default is -1, meaning the last axis of the input.
    input_shape: A list of shape tuples, each not including batch.
    name: String to set the name of the layer.
          If not specified, its name will by default to be a generated string.

    >>> l1 = InputLayer(input_shape=(3, 5))
    creating: createZooKerasInputLayer
    >>> l2 = InputLayer(input_shape=(3, 5))
    creating: createZooKerasInputLayer
    >>> merge = Merge(layers=[l1, l2], mode='sum', name="merge1")
    creating: createZooKerasMerge
    """
    def __init__(self, layers=None, mode="sum", concat_axis=-1,
                 input_shape=None, **kwargs):
        super(Merge, self).__init__(None,
                                    list(layers) if layers else None,
                                    mode,
                                    concat_axis,
                                    input_shape,
                                    **kwargs)


def merge(inputs, mode="sum", concat_axis=-1, name=None):
    """
    Functional merge. Only use this method if you are defining a graph model.
    Used to merge a list of input nodes into a single output node (NOT layers!),
    following some merge mode.

    # Arguments
    inputs: A list of node instances. Must be more than one node.
    mode: Merge mode. String, must be one of: 'sum', 'mul', 'concat', 'ave', 'cos',
          'dot', 'max', 'sub', 'div', 'min'. Default is 'sum'.
    concat_axis: Int, axis to use when concatenating nodes.
                 Only specify this when merge mode is 'concat'.
                 Default is -1, meaning the last axis of the input.
    name: String to set the name of the functional merge.
          If not specified, its name will by default to be a generated string.
    """
    return Merge(mode=mode, concat_axis=concat_axis, name=name)(list(inputs))
