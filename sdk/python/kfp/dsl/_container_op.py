# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from . import _pipeline
from . import _pipeline_param
import re
from typing import Dict


class ContainerOp(object):
    """
    Represents an op implemented by a docker container image.
    表示由docker容器镜像实现的操作。
    """

    def __init__(self, name: str, image: str, command: str = None, arguments: str = None,
                 file_outputs: Dict[str, str] = None, is_exit_handler=False):
        """Create a new instance of ContainerOp.

        Args:
          name: the name of the op. 操作名
          It does not have to be unique within a pipeline
          because the pipeline will generates a unique new name in case of conflicts.
          它不必在pp中是唯一的因为管道将在发生冲突时生成唯一的新名称。
          image: the container image name, such as 'python:3.5-jessie' 镜像名
          command: the command to run in the container. 容器内要运行的命令
              If None, uses default CMD in defined in container. 为空的话 使用容器内默认的
          arguments: the arguments of the command. 命令的参数 The command can include "%s" and supply
              a PipelineParam as the string replacement. For example, ('echo %s' % input_param).
              At container run time the argument will be 'echo param_value'.
          file_outputs: Maps output labels to local file paths. 映射输出标签到本地文件路径
              At pipeline run time, the value of a PipelineParam is saved to its corresponding local file.
              It's one way for outside world to receive outputs of the container.
              在管道运行时，pp参数的值保存到对应的本地文件中。这是外部世界接收容器输出的一种方式。
          is_exit_handler: Whether it is used as an exit handler.它被用作退出处理程序。
        """

        if not _pipeline.Pipeline.get_default_pipeline():
            raise ValueError('Default pipeline not defined.')

        valid_name_regex = r'^[A-Za-z][A-Za-z0-9\s_-]*$'
        if not re.match(valid_name_regex, name):
            raise ValueError(
                'Only letters, numbers, spaces, "_", and "-"  are allowed in name. Must begin with letter: %s' % (name))

        self.human_name = name
        self.name = _pipeline.Pipeline.get_default_pipeline().add_op(self, is_exit_handler)
        self.image = image
        self.command = command
        self.arguments = arguments
        self.is_exit_handler = is_exit_handler
        self.resource_limits = {}
        self.resource_requests = {}
        self.node_selector = {}
        self.volumes = []
        self.volume_mounts = []
        self.env_variables = []
        self.pod_annotations = {}
        self.pod_labels = {}
        self.num_retries = 0

        matches = []
        for arg in (command or []) + (arguments or []):
            match = re.findall(r'{{pipelineparam:op=([\w\s_-]*);name=([\w\s_-]+);value=(.*?)}}', str(arg))
            matches += match

        self.argument_inputs = [_pipeline_param.PipelineParam(x[1], x[0], x[2])
                                for x in list(set(matches))]
        self.file_outputs = file_outputs
        self.dependent_op_names = []

        self.inputs = []
        if self.argument_inputs:
            self.inputs += self.argument_inputs

        self.outputs = {}
        if file_outputs:
            self.outputs = {name: _pipeline_param.PipelineParam(name, op_name=self.name)
                            for name in file_outputs.keys()}

        self.output = None
        if len(self.outputs) == 1:
            self.output = list(self.outputs.values())[0]

    def apply(self, mod_func):
        """
        Applies a modifier function to self. The function should return the passed object.
        This is needed to chain "extention methods" to this class.
        对self应用修饰函数。函数应该返回传递的对象。这是将“扩展方法”链接到该类所必需的。

        Example:
          from kfp.gcp import use_gcp_secret
          task = (
            train_op(...)
              .set_memory_request('1GB')
              .apply(use_gcp_secret('user-gcp-sa'))
              .set_memory_limit('2GB')
          )
        """
        return mod_func(self)

    def after(self, op):
        """
        Specify explicit dependency on another op.
        指定对另一个op的显式依赖。
        """
        self.dependent_op_names.append(op.name)
        return self

    def _validate_memory_string(self, memory_string):
        """
        验证给定的字符串是否符合内存请求或者限制
        Validate a given string is valid for memory request or limit.
        """

        if re.match(r'^[0-9]+(E|Ei|P|Pi|T|Ti|G|Gi|M|Mi|K|Ki){0,1}$', memory_string) is None:
            raise ValueError('Invalid memory string. Should be an integer, or integer followed '
                             'by one of "E|Ei|P|Pi|T|Ti|G|Gi|M|Mi|K|Ki"')

    def _validate_cpu_string(self, cpu_string):
        "验证CPU  Validate a given string is valid for cpu request or limit."

        if re.match(r'^[0-9]+m$', cpu_string) is not None:
            return

        try:
            float(cpu_string)
        except ValueError:
            raise ValueError('Invalid cpu string. Should be float or integer, or integer followed '
                             'by "m".')

    def _validate_positive_number(self, str_value, param_name):
        "Validate a given string is in positive integer format."

        try:
            int_value = int(str_value)
        except ValueError:
            raise ValueError('Invalid {}. Should be integer.'.format(param_name))

        if int_value <= 0:
            raise ValueError('{} must be positive integer.'.format(param_name))

    def add_resource_limit(self, resource_name, value):
        """
        为容器添加资源限制
        Add the resource limit of the container.

        Args:
          resource_name: The name of the resource. It can be cpu, memory, etc.
          value: The string value of the limit.
        """

        self.resource_limits[resource_name] = value
        return self

    def add_resource_request(self, resource_name, value):
        """
        为容器添加资源请求
        Add the resource request of the container.

        Args:
          resource_name: The name of the resource. It can be cpu, memory, etc.
          value: The string value of the request.
        """

        self.resource_requests[resource_name] = value
        return self

    # ==================
    # 和资源相关的设置
    # ==================
    def set_memory_request(self, memory):
        """
        为OP添加内存请求（最小）
        Set memory request (minimum) for this operator.

        Args:
          memory: a string which can be a number or a number followed by one of
                  "E", "P", "T", "G", "M", "K".
        """

        self._validate_memory_string(memory)
        return self.add_resource_request("memory", memory)

    def set_memory_limit(self, memory):
        """
        为OP设置内存限制（最大）
        Set memory limit (maximum) for this operator.

        Args:
          memory: a string which can be a number or a number followed by one of
                  "E", "P", "T", "G", "M", "K".
        """
        self._validate_memory_string(memory)
        return self.add_resource_limit("memory", memory)

    def set_cpu_request(self, cpu):
        """
        为OP设置CPU请求（最小）
        Set cpu request (minimum) for this operator.

        Args:
          cpu: A string which can be a number or a number followed by "m", which means 1/1000.
        """

        self._validate_cpu_string(cpu)
        return self.add_resource_request("cpu", cpu)

    def set_cpu_limit(self, cpu):
        """
        为OP设置CPU限制（最大）
        Set cpu limit (maximum) for this operator.

        Args:
          cpu: A string which can be a number or a number followed by "m", which means 1/1000.
        """

        self._validate_cpu_string(cpu)
        return self.add_resource_limit("cpu", cpu)

    def set_gpu_limit(self, gpu, vendor="nvidia"):
        """
        设置操作的GPU限制 支持GPU类型为  'nvidia' (default), and 'amd'
        Set gpu limit for the operator. This function add '<vendor>.com/gpu' into resource limit.
        Note that there is no need to add GPU request. GPUs are only supposed to be specified in
        the limits section. See https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/.

        Args:
          gpu: A string which must be a positive number. 正数
          vendor: Optional. A string which is the vendor of the requested gpu. The supported values
            are: 'nvidia' (default), and 'amd'.
        """

        self._validate_positive_number(gpu, 'gpu')  # 验证GPU值 是否为正数
        if vendor != 'nvidia' and vendor != 'amd':
            raise ValueError('vendor can only be nvidia or amd.')

        return self.add_resource_limit("%s.com/gpu" % vendor, gpu)  # nvidia.com/gpu 1

    # ==================
    # 和存储相关的设置
    # ==================
    def add_volume(self, volume):
        """
        为容器添加k8s存储卷
        Add K8s volume to the container

        Args:
          volume: Kubernetes volumes
          For detailed spec, check volume definition
          https://github.com/kubernetes-client/python/blob/master/kubernetes/client/models/v1_volume.py
        """

        self.volumes.append(volume)
        return self

    def add_volume_mount(self, volume_mount):
        """
        为容器添加挂载的存储卷
        Add volume to the container

        Args:
          volume_mount: Kubernetes volume mount
          For detailed spec, check volume mount definition
          https://github.com/kubernetes-client/python/blob/master/kubernetes/client/models/v1_volume_mount.py
        """

        self.volume_mounts.append(volume_mount)
        return self

    def add_env_variable(self, env_variable):
        """
        为容器添加环境变量
        Add environment variable to the container.

        Args:
          env_variable: Kubernetes environment variable
          For detailed spec, check environment variable definition
          https://github.com/kubernetes-client/python/blob/master/kubernetes/client/models/v1_env_var.py
        """

        self.env_variables.append(env_variable)
        return self

    # ==================
    # 和POD相关的设置
    # ==================
    def add_node_selector_constraint(self, label_name, value):
        """
        添加节点约束  每个约束条件是成对的键值对标签
        Add a constraint for nodeSelector. Each constraint is a key-value pair label. For the
        为了容器运行在一个合适的节点上， 节点必须符合每一个最为标签出现的约束条件
        container to be eligible to run on a node, the node must have each of the constraints appeared
        as labels.

        Args:
          label_name: The name of the constraint label.  （键值对形式的)约束条件
          value: The value of the constraint label.  约束条件的值
        """

        self.node_selector[label_name] = value
        return self

    def add_pod_annotation(self, name: str, value: str):
        """
        增加pod的源数据注解
        Adds a pod's metadata annotation.

        Args:
          name: The name of the annotation.
          value: The value of the annotation.
        """

        self.pod_annotations[name] = value
        return self

    def add_pod_label(self, name: str, value: str):
        """
        添加pod的源数据标签
        Adds a pod's metadata label.

        Args:
          name: The name of the label.
          value: The value of the label.
        """

        self.pod_labels[name] = value
        return self

    def set_retry(self, num_retries: int):
        """
        设置任务重试的次数，直到宣告失败为止。
        Sets the number of times the task is retried until it's declared failed.

        Args:
          num_retries: Number of times to retry on failures.
        """

        self.num_retries = num_retries
        return self

    def __repr__(self):
        return str({self.__class__.__name__: self.__dict__})
