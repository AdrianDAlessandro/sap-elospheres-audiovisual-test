# from .av_renderer_control import AVRendererControl
import avrenderercontrol.av_renderer_control as avrc
import confuse
import pathlib
import numpy as np
import ipaddress
import os
import errno
from pythonosc import udp_client
import time
import subprocess
import sys

# helper functions
# leading underscore avoids being imported


def _is_valid_ipaddress(address_to_test):
    """Private function to check validity of an ip address"""
    try:
        parsed_address = ipaddress.ip_address(address_to_test)
        print('parsed address:' + str(parsed_address))
        return True
    except ValueError as err:
        print(err)
        print('Invalid address:', address_to_test)
        return False


def check_path_is_file(pathlib_path):
    if not pathlib_path.is_file():
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), str(pathlib_path))


def convert_windows_path_to_wsl(pathlib_win_path):
    wsl_command = ("wsl bash -c \"wslpath '"
                   + str(pathlib_win_path)
                   + "'\"")
    try:
        result = subprocess.run(wsl_command,
                                capture_output=True,
                                check=True,
                                text=True)
        return result.stdout.rstrip()

    except subprocess.CalledProcessError as error:
        print('Path conversion using wslpath failed')
        print(wsl_command)
        raise error


class ListeningEffortPlayerAndTascarUsingOSCBase(avrc.AVRendererControl):
    """
    Base class to implement core functionality of co-ordinating the unity-based
    visual display with headtracking data sent via osc to tascar-based audio
    renderer running on windows subsytem for linux
    """
    def __init__(self):
        # get the IP addresses
        app_name = 'ListeningEffortPlayerAndTascarUsingOSC'
        self.moduleConfig = confuse.Configuration(app_name, __name__)

    # implement conext manager magic
    def __enter__(self):
        return self

    # implement conext manager magic
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_scene()
        self.close_osc()

    def setup_osc(self):
        # get the tascar ip address
        # if specified in the config use it, otherwise look in enviornment
        # variable
        tascar_ipaddress = self.moduleConfig['tascar']['ipaddress'].get(str)
        print('config tascar.ipaddress:' + tascar_ipaddress)
        if not _is_valid_ipaddress(tascar_ipaddress):
            env_variable_name = self.moduleConfig['tascar']['ipenvvariable'] \
                .get(str)
            filename = os.environ.get(env_variable_name)
            print('Reading tascar IP address from ' + filename)
            with open(filename, "r") as myfile:
                tascar_ipaddress = myfile.readline().strip()
            print('env {}: {}'.format(env_variable_name, tascar_ipaddress))
            if not _is_valid_ipaddress(tascar_ipaddress):
                # failed to get a valid ipaddress
                print(tascar_ipaddress)
                raise ValueError
            # store it in config in case we need it again
            self.moduleConfig['tascar']['ipaddress'] = tascar_ipaddress

        sampler_ipaddress = self.moduleConfig['sampler']['ipaddress'].get(str)
        print('config tascar.ipaddress:' + sampler_ipaddress)
        if not _is_valid_ipaddress(sampler_ipaddress):
            env_variable_name = self.moduleConfig['tascar']['ipenvvariable'] \
                .get(str)
            filename = os.environ.get(env_variable_name)
            print('Reading tascar IP address from ' + filename)
            with open(filename, "r") as myfile:
                sampler_ipaddress = myfile.readline().strip()
            print('env {}: {}'.format(env_variable_name, sampler_ipaddress))
            if not _is_valid_ipaddress(sampler_ipaddress):
                # failed to get a valid ipaddress
                print(sampler_ipaddress)
                raise ValueError
            # store it in config in case we need it again
            self.moduleConfig['sampler']['ipaddress'] = sampler_ipaddress

        # TODO: check validity of all ip addresses
        # open the OSC comms
        self.video_client = udp_client.SimpleUDPClient(
            self.moduleConfig['unity']['ipaddress'].get(str),
            self.moduleConfig['unity']['oscport'].get(int))
        self.tascar_client = udp_client.SimpleUDPClient(
            self.moduleConfig['tascar']['ipaddress'].get(str),
            self.moduleConfig['tascar']['oscport'].get(int))
        self.sampler_client1 = udp_client.SimpleUDPClient(
            self.moduleConfig['sampler']['ipaddress'].get(str),
            self.moduleConfig['sampler']['source1']['oscport'].get(int))
        self.sampler_client2 = udp_client.SimpleUDPClient(
            self.moduleConfig['sampler']['ipaddress'].get(str),
            self.moduleConfig['sampler']['source2']['oscport'].get(int))
        self.sampler_client3 = udp_client.SimpleUDPClient(
            self.moduleConfig['sampler']['ipaddress'].get(str),
            self.moduleConfig['sampler']['source3']['oscport'].get(int))

        # tell unity where to send the head rotation data
        self.video_client.send_message("/set_client_address", [
            self.moduleConfig['tascar']['ipaddress'].get(str),
            self.moduleConfig['tascar']['oscport'].get(int)
            ])

    def close_osc(self):
        # this isn't really necessary but avoids warnings in unittest
        if hasattr(self, 'video_client'):
            self.video_client._sock.close()
        if hasattr(self, 'tascar_client'):
            self.tascar_client._sock.close()
        if hasattr(self, 'sampler_client1'):
            self.sampler_client1._sock.close()
        if hasattr(self, 'sampler_client2'):
            self.sampler_client2._sock.close()
        if hasattr(self, 'sampler_client3'):
            self.sampler_client3._sock.close()

    def start_scene(self):
        """
        Basic implementation - subclasses may need to override
        """
        if self.state == avrc.AVRCState.READY_TO_START:

            wsl_command = 'wsl ' \
                + '-u root bash -c \"/usr/bin/tascar_cli ' \
                + str(self.tascar_scn_file_wsl_path) \
                + '\"'
            # print(wsl_command)
            self.tascar_process = subprocess.Popen(
                wsl_command, creationflags=subprocess.CREATE_NEW_CONSOLE)

            # give tascar a chance to start
            time.sleep(0.3)

            # check process is running
            if self.tascar_process.poll() is not None:
                # oh dear, it's not running!
                # try again with settings which will allow us to debug
                self.tascar_process = subprocess.Popen(
                    wsl_command, creationflags=subprocess.CREATE_NEW_CONSOLE,
                    stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                    text=True)
                outs, errs = self.tascar_process.communicate()
                print('stdout:')
                if outs is not None:
                    print(outs)
                    # for line in outs:
                    #     print(line)
                print('stderr:')
                if errs is not None:
                    print(errs)

            # get the process pid in wsl land
            wsl_command = 'wsl -u root bash -c \"' \
                + 'pidof tascar_cli' \
                + '\"'
            try:
                result = subprocess.run(wsl_command,
                                        capture_output=True,
                                        check=True,
                                        text=True)
                self.tascar_pid_as_str = result.stdout.rstrip()
                print('tascar_cli running with pid: ' + self.tascar_pid_as_str)

            except subprocess.CalledProcessError:
                # we got an error, which means we couldn't get the pid
                # nothing to be done but exit gracefully
                print('couldn''t get pid of tascar_cli')
                sys.exit("probably tascar_cli failed to start")

            # one shot for the background
            self.video_client.send_message(
                "/video/play", [0, str(self.skybox_absolute_path)])
            self.tascar_client.send_message("/transport/locate", [0.0])
            self.tascar_client.send_message("/transport/start", [])
            self.state = avrc.AVRCState.ACTIVE
        else:
            # TODO: Can we automate progressing through states rather than just
            # falling over?
            raise RuntimeError("Cannot start scene before it has been setup")

    def stop_scene(self):
        if self.state is avrc.AVRCState.ACTIVE:
            # end tascar_cli process directly using linux kill
            # this avoids audio glitches
            wsl_command = 'wsl ' \
                + '-u root bash -c \"kill ' \
                + self.tascar_pid_as_str \
                + '\"'
            # print(wsl_command)
            subprocess.run(wsl_command)

            # make sure it really has finished
            if self.tascar_process.poll() is None:
                self.tascar_process.terminate()
            self.state = avrc.AVRCState.TERMINATED


class TargetToneInNoise(ListeningEffortPlayerAndTascarUsingOSCBase):
    """
    Demo to show probe level control without requiring speech files
    """

    # Override constructor to allow settings to be passed in
    def __init__(self, config):
        app_name = 'TargetToneInNoise'
        self.moduleConfig = confuse.Configuration(app_name, __name__)
        self.state = avrc.AVRCState.INIT

        # carry on and do the congiguration
        if config is not None:
            self.load_config(config)

    def load_config(self, config):
        # grab the bits we need
        self.data_root_dir = config["root_dir"]
        self.tascar_scn_file = pathlib.Path(self.data_root_dir,
                                            'tascar_scene.tsc')
        check_path_is_file(self.tascar_scn_file)
        self.tascar_scn_file_wsl_path = convert_windows_path_to_wsl(
            self.tascar_scn_file
        )

        self.skybox_absolute_path = pathlib.Path(self.data_root_dir,
                                                 'skybox.mp4')
        check_path_is_file(self.skybox_absolute_path)

        # if we get to here we assume the configuration was successful
        self.state = avrc.AVRCState.CONFIGURED

        # carry on do the setup
        self.setup()

    def setup(self):
        """Inherited public interface for setup"""
        if self.state == avrc.AVRCState.CONFIGURED:
            try:
                self.setup_osc()
            except Exception as err:
                print('Encountered error in setup_osc():')
                print(err)
                print('Perhaps configuration had errors...reload config')
                self.state = avrc.AVRCState.INIT
            else:
                self.state = avrc.AVRCState.READY_TO_START
        else:
            raise RuntimeError('Cannot call setup() before it has been '
                               'configured')

    def set_probe_level(self, probe_level):
        pass

    def present_trial(self, stimulus_id):
        # unmute target
        self.tascar_client.send_message("/main/target/mute", [0])
        time.sleep(0.5)
        self.tascar_client.send_message("/main/target/mute", [1])


class TargetSpeechTwoMaskers(ListeningEffortPlayerAndTascarUsingOSCBase):
    """
    Demo to show speech probe with point source maskers - all materials
    provided as files which are listed in txt files. Txt files have relative
    paths hard coded into the tascar_scene.tsc file but the location of the
    paths to the data files are absolute so can be anywhere.
    """

    # Override constructor to allow settings to be passed in
    def __init__(self, config):
        app_name = 'TargetSpeechTwoMaskers'
        self.moduleConfig = confuse.Configuration(app_name, __name__)
        self.state = avrc.AVRCState.INIT

        # carry on and do the congiguration
        if config is not None:
            self.load_config(config)

    def load_config(self, config):
        # grab the bits we need
        self.data_root_dir = config["root_dir"]

        # tascar scene
        self.tascar_scn_file = pathlib.Path(self.data_root_dir,
                                            'tascar_scene.tsc')
        check_path_is_file(self.tascar_scn_file)
        self.tascar_scn_file_wsl_path = convert_windows_path_to_wsl(
            self.tascar_scn_file)

        # skybox
        self.skybox_absolute_path = pathlib.Path(self.data_root_dir,
                                                 'skybox.mp4')
        check_path_is_file(self.skybox_absolute_path)

        # delay between maskers and target
        self.pre_target_delay = config["pre_target_delay"]
        # TODO: validate

        # read in and validate video list
        self.present_target_video = config["present_target_video"]
        if self.present_target_video:
            self.target_video_paths = []
            with open(pathlib.Path(self.data_root_dir,
                                   config["target_video_list_file"]), 'r') as f:
                for line in f:
                    video_path = pathlib.Path(line.rstrip())
                    check_path_is_file(video_path)
                    self.target_video_paths.append(video_path)




        # get the masker directions

        # if we get to here we assume the configuration was successful
        self.state = avrc.AVRCState.CONFIGURED

        # carry on do the setup
        self.setup()

    def setup(self):
        """Inherited public interface for setup"""
        print('Entered setup()')
        if self.state == avrc.AVRCState.CONFIGURED:
            try:
                self.setup_osc()
            except Exception as err:
                print('Encountered error in setup_osc():')
                print(err)
                print('Perhaps configuration had errors...reload config')
                self.state = avrc.AVRCState.INIT

            # continue with setup
            self.target_source_name = 'source2'
            self.masker1_source_name = 'source1'
            self.masker2_source_name = 'source3'
            self.target_linear_gain = 1.0
            self.masker_linear_gain = 1.0

            # TODO: set the positions of the maskers

            # save state
            self.state = avrc.AVRCState.READY_TO_START
        else:
            raise RuntimeError('Cannot call setup() before it has been '
                               'configured')

    def set_probe_level(self, probe_level):
        """Probe level is SNR in dB

        This is interpreted as the relative gain to be applied to the target
        """
        self.target_linear_gain = np.power(10.0, (probe_level/20.0))

    def present_trial(self, stimulus_id):
        # print('Entered present_trial() with stimulus: ' + str(stimulus_id))

        # start maskers
        msg_address = ("/" + self.masker1_source_name
                       + "/" + str(stimulus_id+1)
                       + "/add")
        msg_contents = [1, self.masker_linear_gain]  # loop_count, linear_gain
        # print(msg_address)
        self.sampler_client1.send_message(msg_address, msg_contents)

        msg_address = ("/" + self.masker2_source_name
                       + "/" + str(stimulus_id+1)
                       + "/add")
        msg_contents = [1, self.masker_linear_gain]  # loop_count, linear_gain
        # print(msg_address)
        self.sampler_client3.send_message(msg_address, msg_contents)

        # pause
        time.sleep(self.pre_target_delay)

        # start target
        # - video first
        if self.present_target_video:
            # msg_contents = [video player id, video file]
            msg_contents = [2, str(self.target_video_paths[stimulus_id])]
            self.video_client.send_message("/video/play", msg_contents)

        msg_address = ("/" + self.target_source_name
                       + "/" + str(stimulus_id+1)
                       + "/add")
        # - audio after a short pause to get lip sync right
        time.sleep(0.15)
        msg_contents = [1, self.target_linear_gain]  # loop_count, linear_gain
        # print(msg_address + str(msg_contents))
        self.sampler_client2.send_message(msg_address, msg_contents)
