"""A thread worker function running CAREamics training."""
from typing import Generator, Optional
from queue import Queue
from threading import Thread

from napari.qt.threading import thread_worker
import napari.utils.notifications as ntf

from careamics import CAREamist
from careamics.config.support import SupportedAlgorithm

from careamics_napari.careamics_utils.callback import UpdaterCallBack
from careamics_napari.careamics_utils.configuration import create_configuration
from careamics_napari.signals import (
    TrainUpdate,
    TrainUpdateType,
    TrainingState, 
    TrainConfigurationSignal
)


# TODO register CAREamist to continue training and predict 
# TODO how to load pre-trained?
# TODO pass careamist here if it already exists?
@thread_worker
def train_worker(
    config_signal: TrainConfigurationSignal,
    careamist: Optional[CAREamist] = None,
) -> Generator[TrainUpdate, None, None]:

    # create update queue
    update_queue = Queue(10)

    # start training thread
    training = Thread(
        target=_train, 
        args=(
            config_signal, 
            update_queue,
            careamist,
        )
    )
    training.start()

    # look for updates
    while True:
        update: TrainUpdate = update_queue.get(block=True)
        
        yield update

        if (
            (update.type == TrainUpdateType.STATE and update.value == TrainingState.DONE)
            or (update.type == TrainUpdateType.EXCEPTION)
        ):
            break

def _push_exception(queue: Queue, e: Exception) -> None:
    queue.put(TrainUpdate(TrainUpdateType.EXCEPTION, e))

def _train(
        config_signal: TrainConfigurationSignal, 
        update_queue: Queue, 
        careamist: Optional[CAREamist] = None
) -> None:
    
    # get configuration
    config = create_configuration(config_signal)

    # Create CAREamist
    if careamist is None:
        careamist = CAREamist(
            source=config, 
            callbacks=[UpdaterCallBack(update_queue)]
        )
    else:
        # only update the number of epochs
        careamist.cfg.training_config.num_epochs = config.training_config.num_epochs

        if config_signal.layer_val == "" and config_signal.path_val == "":
            ntf.show_error(
                "Continuing training is currently not supported without explicitely "
                "passing validation. The reason is that otherwise, the data used for "
                "validation will be different and there will be data leakage in the "
                "training set."
            )
        
    # Register CAREamist
    update_queue.put(TrainUpdate(TrainUpdateType.CAREAMIST, careamist))

    # Format data
    train_data_target = None
    val_data_target = None

    if config_signal.load_from_disk:

        if config_signal.path_train == "":
            _push_exception(
                update_queue, 
                ValueError(
                    "Training data path is empty."
                )
            )
            return

        train_data = config_signal.path_train
        val_data = config_signal.path_val if config_signal.path_val != "" else None

        if train_data == val_data:
            val_data = None

        if config_signal.algorithm != SupportedAlgorithm.N2V:
            if config_signal.path_train_target == "":
                _push_exception(
                    update_queue, 
                    ValueError(
                        "Training target data path is empty."
                    )
                )
                return

            train_data_target = config_signal.path_train_target

            if val_data is not None:
                val_data_target = (
                    config_signal.path_val_target 
                    if config_signal.path_val_target != "" 
                    else None
                )

    else:
        if config_signal.layer_train is None:
            _push_exception(
                update_queue, 
                ValueError(
                    "Training data path is empty."
                )
            )

        train_data = config_signal.layer_train.data
        val_data = (
            config_signal.layer_val.data 
            if config_signal.layer_val is not None 
            else None
        )

        if train_data == val_data:
            val_data = None

        if config_signal.algorithm != SupportedAlgorithm.N2V:

            if config_signal.layer_train_target is None:
                _push_exception(
                    update_queue, 
                    ValueError(
                        "Training target data path is empty."
                    )
                )
                return

            train_data_target = config_signal.layer_train_target.data

            if val_data is not None:
                val_data_target = (
                    config_signal.layer_val_target.data
                    if config_signal.layer_val_target is not None 
                    else None
                )

    # TODO add val percentage and val minimum
    # Train CAREamist
    try:
        careamist.train(
            train_source=train_data, 
            val_source=val_data,
            train_target=train_data_target,
            val_target=val_data_target,
        )

        # # TODO can we use this to monkey patch the training process?
        # update_queue.put(Update(UpdateType.MAX_EPOCH, 10_000 // 10))
        # update_queue.put(Update(UpdateType.MAX_BATCH, 10_000))
        # for i in range(10_000):

        #     # if stopper.stop:
        #     #     update_queue.put(Update(UpdateType.STATE, TrainingState.STOPPED))
        #     #     break

        #     if i % 10 == 0:
        #         update_queue.put(Update(UpdateType.EPOCH, i // 10))
        #         print(i)

        #     update_queue.put(Update(UpdateType.BATCH, i))

        #     time.sleep(0.2) 

    except Exception as e:
        update_queue.put(
            TrainUpdate(TrainUpdateType.EXCEPTION, e)
        )

    update_queue.put(TrainUpdate(TrainUpdateType.STATE, TrainingState.DONE))