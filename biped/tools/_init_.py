import os 

def main_folder_path():
    complete_path = os.path.realpath(__file__)
    main_path = complete_path.split("\scripts")[0]
    print(complete_path)
    print(main_path)
    return main_path

main_folder_path()