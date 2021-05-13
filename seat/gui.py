import argparse
from datetime import datetime
import pandas as pd
import pathlib
import PySimpleGUI as sg
import sys
import yaml

import seat
import util


# class ExperimentBlockSelector(csv_file):
def gui(csv_file):
    # read the csv file
    df = pd.read_csv(csv_file)
    print(df)
    
    subject_id_list = df.subject_id.unique().tolist()
    print(subject_id_list)
    
    # define the gui
    label_size = (8,1)
    key_meta_name = "subject_name"
    key_meta_age = "subject_age"
    key_meta_sex = "subject_sex"
    meta_keys = [key_meta_name, key_meta_age, key_meta_sex]
    key_subject_combo = "-subject-"
    key_block_combo = "-block-"
    key_config_text = "-config-"
    key_run_button = "-run-"
    layout = [[sg.Text('Enter participant details (optional, unvalidated)')],
              [sg.Text('Name: ',size=label_size),
               sg.Input(key=key_meta_name)],
              [sg.Text('Age: ',size=label_size),
               sg.Input(key=key_meta_age)],              
              [sg.Text('Sex: ',size=label_size),
               sg.Input(key=key_meta_sex)],
              [sg.Text('Select the subject then the block number')],
              [sg.Text('Subject: ',size=label_size),
               sg.Combo(subject_id_list, key=key_subject_combo, enable_events=True, size=(8,1))],
              [sg.Text('Block: ',size=label_size),
               sg.Combo([''], key=key_block_combo, enable_events=True, size=(8,1), disabled=True)],
              [sg.Text('Config: ',size=label_size),
               sg.Input('', key=key_config_text, size=(60,1), justification='right',disabled=True,text_color='grey')],
              [sg.Button('Run', key=key_run_button, focus=True,
                             disabled=True)]
             ]

    window = sg.Window('SEAT block selector', layout,
                                keep_on_top=False,
                                return_keyboard_events=True,
                                # use_default_focus=False,
                                finalize=True)

    while True:             # Event Loop
        event, values = window.Read()
        # print(event, values)
        
        if event == sg.WIN_CLOSED:
            window.close()
            return
        elif event == key_subject_combo:
            subject_id = values[key_subject_combo]
            # subject_id = values
            print(f'Selected subject {subject_id}')
            # populate block combo
            block_id_list = df[df.subject_id==subject_id].block_id.unique().tolist()
            window[key_block_combo].Update(values=block_id_list)
            window[key_block_combo].Update(value='', disabled=False)
            window[key_config_text].Update(value='')
            window[key_run_button].Update(disabled=True)           
        elif event == key_block_combo:
            block_id = values[key_block_combo]
            print(f'Selected block {block_id}')
            subject_id = values[key_subject_combo]
            # find a matching directory
            search_str = f'{subject_id}_{block_id}_*/config.yml'
            print(search_str)
            matches = sorted(pathlib.Path(csv_file).parent.glob(search_str))
            print(matches)
            if len(matches) == 1:
                window[key_config_text].Update(value=str(matches[0]))
                window[key_run_button].Update(disabled=False)
            else:
                window[key_config_text].Update(value='')
                window[key_run_button].Update(disabled=True)
        elif event == key_run_button:
            # prepare metadata as single row dataframe
            subject_data = dict([(key, window[key].get()) for key in meta_keys])
            # n.b. need to wrap dict in list
            subject_data = pd.DataFrame.from_records([subject_data])

            
            
            config_file = pathlib.Path(window[key_config_text].get())
            print(config_file)
            datestr = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = pathlib.Path(config_file.parent, datestr)
            
            # by now we should have a value for out_dir
            try:
                out_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                print(f'Output directory {out_dir} already exists.')
                break
            
            with open(config_file, 'r') as f:
                block_config = yaml.safe_load(f)
                if ("App" in block_config):
                    raise NotImplementedError("Deal with App.log_dir")
                else:
                    block_config["App"] = {"log_dir": str(out_dir)}
                    
                try:
                    seat.run_block(block_config, subject_data=subject_data)
                except Exception as e:
                    # tb = traceback.format_exc()
                    print(f'An error happened.  Here is the info:', e)
                    sg.popup_error(f'Something went wrong running the test!\nCheck the console for more information.', e)
                        

if __name__ == '__main__':
    # parse the command line inputs
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file",
                        help="conditions file (.csv)")
    # parser.add_argument("-o", "--out-dir",
    #                     help="output directory for logs/results")
    args = parser.parse_args()
    print(args)
    
    # file
    # - use the provided option otherwise pop a dialoge to choose it
    if args.file is not None:
        file = args.file
        print('Config file: ' + file)
    else:
        # get file
        file = sg.popup_get_file(
            'Choose the condition specification file',
            file_types=(('csv', '*.csv'),)
            )
    if file is None:
        sys.exit()
    else:
        file = pathlib.Path(file)
        try:
            util.check_path_is_file(file)
        except FileNotFoundError:
            print('No csv file found at ' + str(file))
            sys.exit()
            
    gui(file)