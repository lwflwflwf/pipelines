# XGBoost Distributed Trainer and Predictor Package


This directory contains code and building script to build a generic XGBoost model and perform
predictions on it.

XGBoost4j package currently requires building from source
(https://github.com/dmlc/xgboost/issues/1807), as well as the spark layer and user code on top
of it. To do so, get a GCE VM (debian 8), and run
[xgb4j_build.sh](xgb4j_build.sh) on it. The script contains steps to compile/install cmake,
git clone xgboost repo, copy sources, and build a jar package that can run in a spark environment.
This is only tested on Google Dataproc cluster.
#######
该目录包含代码和构建脚本，用于构建通用的XGBoost模型并对其执行预测。XGBoost4i包目前需要从源代码(https://github.com/dmlc/xgboostissues/1807)构建，以及在其上的spark层和用户代码。这样做。获取GCE VM (debian 8)，并在其上运行xgb4i build.sh。该脚本包含编译/安装cmake、git克隆xgboost repo、复制源代码和构建可以在spark环境中运行的jar包的步骤。这只在谷歌Dataproc集群上测试。