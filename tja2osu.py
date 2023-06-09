from enum import Enum
import os
import re
import copy
from fractions import Fraction
import math
import sys

beatmap = '''osu file format v14

[General]
AudioFilename: {}
AudioLeadIn: 0
PreviewTime: {}
Countdown: 0
SampleSet: Normal
StackLeniency: 0.7
Mode: 1
LetterboxInBreaks: 0
WidescreenStoryboard: 0

[Editor]
DistanceSpacing: 0.8
BeatDivisor: 7
GridSize: 32
TimelineZoom: 1

[Metadata]
Title: {}
TitleUnicode: {}
Artist: Unknown
ArtistUnicode: Unknown
Creator: Unknown
Version: {}
Source:
Tags: tja
BeatmapID:0
BeatmapSetID:-1

[Difficulty]
HPDrainRate:5
CircleSize:5
OverallDifficulty:9
ApproachRate:5
SliderMultiplier:1.4
SliderTickRate:1

[Events]
//Background and Video events
//Break Periods
//Storyboard Layer 0 (Background)
//Storyboard Layer 1 (Fail)
//Storyboard Layer 2 (Pass)
//Storyboard Layer 3 (Foreground)
//Storyboard Layer 4 (Overlay)
//Storyboard Sound Samples'''

formats = {
    'timing': '{},{},{},1,0,100,{},{}', # time, length, meter, inherited, kiai
    'don': '256,192,{},1,0,0:0:0:0:', # time
    'ka': '256,192,{},1,2,0:0:0:0:', # time
    'bigdon': '256,192,{},1,4,0:0:0:0:', # time
    'bigka': '256,192,{},1,12,0:0:0:0:', # time
    'slide': '256,192,{},2,0,L|{}:192,1,{}', # time, x, beatlength
    'bigslide': '256,192,{},2,1,L|{}:192,1,{}', # time, x, beatlength
    'spin': '256,192,{},12,0,{}', # time, end
}

course_map = {
    'Easy': 0,
    'Normal': 1,
    'Hard': 2,
    'Oni': 3,
    'Edit': 4,
    '0': 0,
    '1': 1,
    '2': 2,
    '3': 3,
    '4': 4
}

course_name = ['Kantan', 'Futsuu', 'Muzukashii', 'Oni', 'Inner Oni']
branch_name = ['Normal', 'Expert', 'Master']


class Metadata:
    title: str
    titlejp: str
    subtitle: str
    subtitlejp: str
    bpm: float
    offset: float
    demostart: float
    wave: str
    branch: list[bool]

    def __init__(self):
        self.title = ''
        self.titlejp = None
        self.subtitle = ''
        self.subtitlejp = None
        self.bpm = 120
        self.offset = 0
        self.demostart = 0
        self.wave = ''
        self.branch = [True, False, False]

metadata = Metadata()

class Param:
    time: float
    bpm: float
    beat_length: float
    meter: list[int]
    scroll: float
    gogo: bool
    line: bool

    def __init__(self):
        self.time = 0
        self.bpm = 120
        self.beat_length = 60000 / 120
        self.meter = [4, 4]
        self.scroll = 1
        self.gogo = False
        self.line = True

    def beat_per_char(self, char: int):
        return self.meter[0] / char

    def time_per_char(self, char: int):
        return self.beat_per_char(char) * self.beat_length

    def slide_length_per_char(self, char: int):
        return self.beat_per_char(char) * 4 / self.meter[1] * self.scroll * 1.4 * 100

    @property
    def measure_equivalent_beat(self):
        return self.meter[0] / self.meter[1] * 4

class Status(Enum):
    main_metadata = 0
    course_metadata = 1
    course_chart = 2
    skipping = 3

def parse(lines: list[str]):
    backup = []
    osu = []
    uninherited_changed = False
    inherited_changed = False
    courses = [None, None, None, None, None]
    section = [None, None, None]
    param = Param()
    # metadata = Metadata()
    course_metadata = Metadata()
    # status = [Status.main_metadata, {}]
    status = Status.main_metadata
    course = 0
    player = 1
    measure = []
    long_start = 0
    in_slide = False
    slide_length = 0
    char = 0
    long_type = ''

    for line in lines:
        line = re.sub(r'//.*', '', line)
        line = line.strip()
        if len(line) == 0:
            continue

        if line.startswith('COURSE') and status != Status.course_metadata:
            status = Status.course_metadata 
        elif line.startswith('#START') and status == Status.course_metadata:
            status = Status.course_chart
        elif line.startswith('#END') and status == Status.course_chart:
            courses[course].append(section)

        if status == Status.main_metadata:
            data = list(map(lambda x: x.strip(), line.split(':')))
            if data[1] == '':
                continue
            match data[0]:
                case 'TITLE':
                    metadata.title = data[1]
                case 'TITLEJA':
                    metadata.titlejp = data[1]
                case 'SUBTITLE':
                    metadata.subtitle = data[1]
                case 'SUBTITLEJA':
                    metadata.subtitlejp = data[1]
                case 'BPM':
                    metadata.bpm = float(data[1])
                case 'OFFSET':
                    metadata.offset = float(data[1])
                case 'DEMOSTART':
                    metadata.demostart = float(data[1])
                case 'WAVE':
                    metadata.wave = data[1]

        elif status == Status.course_metadata:
            data = list(map(lambda x: x.strip(), line.split(':')))
            match data[0]:
                case 'COURSE':
                    param = Param()
                    param.bpm = metadata.bpm
                    param.time = -metadata.offset * 1000 - 25
                    course = course_map[data[1].capitalize()]
                    branch = 0
                    if courses[course] is None:
                        courses[course] = []
                case 'STYLE':
                    print(f'\nSTYLE is not supported. skipped {course_name[course]}')
                    status = Status.skipping
        
        elif status == Status.course_chart:
            if line.startswith('#') and line.endswith(','):
                measure.append(line[:-1])
                line = '0,'
            if line == ',':
                line = '0,'

            if line.startswith('#START'):
                measure.append(f'#BPMCHANGE {param.bpm}')
            measure.append(line)
            if not line.startswith('#'):
                char += len(line)
            if not line.endswith(','):
                continue
            char -= 1

                    

            # continuous irregular meter
            if not param.measure_equivalent_beat.is_integer():
                uninherited_changed = True
                

            for l in measure:
                if section[branch] is None:
                    section[branch] = [[], []]

                if l.startswith('#'):
                    data = list(map(lambda x: x.strip(), l.split(' ')))
                    match data[0]:
                        case '#START':
                            if len(data) > 1:
                                print(f'\ndouble player is not supported. skipped {course_name[course]}')
                                status = Status.skipping
                            section = [None, None, None]
                        case '#DELAY':
                            param.time += float(data[-1])
                        case '#BPMCHANGE':
                            param.bpm = float(data[-1])
                            param.beat_length = 60000 / param.bpm * 4 / param.meter[1]
                            uninherited_changed = True
                        case '#MEASURE':
                            param.meter = list(map(int, data[-1].split('/')))
                            param.beat_length = 60000 / param.bpm * 4 / param.meter[1]
                            uninherited_changed = True
                        case '#SCROLL':
                            param.scroll = float(data[-1])
                            inherited_changed = True
                        case '#GOGOSTART':
                            param.gogo = True
                            inherited_changed = True
                        case '#GOGOEND':
                            param.gogo = False
                            inherited_changed = True
                        case '#BARLINEOFF':
                            param.line = False
                            uninherited_changed = True
                        case '#BARLINEON':
                            param.line = True
                            uninherited_changed = True
                        case '#BRANCHSTART':
                            branch = 0
                            backup = param
                            courses[course].append(section)
                            section = [None, None, None]
                        case '#N':
                            branch = 0
                            param = copy.deepcopy(backup)
                        case '#E':
                            metadata.branch[1] = True
                            branch = 1
                            param = copy.deepcopy(backup)
                        case '#M':
                            metadata.branch[2] = True
                            branch = 2
                            param = copy.deepcopy(backup)
                        case '#BRANCHEND':
                            branch = 0
                            time = param.time
                            param = copy.deepcopy(backup)
                            param.time = time
                            courses[course].append(section)
                            section = [None, None, None]
                        # case '#END':
                        #     courses[course].append(section)
                        
                else:
                    if uninherited_changed:
                        effect = int(param.gogo) * 8 + int(param.line)
                        section[branch][0].append(
                            formats['timing'].format(
                                int(param.time),
                                round(60000 / param.bpm, 2),
                                math.ceil(param.measure_equivalent_beat),
                                1,
                                effect))
                    if inherited_changed or (uninherited_changed and param.scroll != 1):
                        section[branch][0].append(
                            formats['timing'].format(
                                int(param.time),
                                round(-100 / param.scroll, 2),
                                math.ceil(param.measure_equivalent_beat),
                                0,
                                int(param.gogo)))
                    inherited_changed = False
                    uninherited_changed = False

                    for i, n in enumerate(l):
                        if in_slide:
                            slide_length += param.slide_length_per_char(char)

                        match n:
                            case '1':
                                section[branch][1].append(
                                    formats['don'].format(int(param.time)))
                            case '2':
                                section[branch][1].append(
                                    formats['ka'].format(int(param.time)))
                            case '3':
                                section[branch][1].append(
                                    formats['bigdon'].format(int(param.time)))
                            case '4':
                                section[branch][1].append(
                                    formats['bigka'].format(int(param.time)))
                            case '5':
                                long_start = param.time
                                long_type = 'slide'
                                in_slide = True
                            case '6':
                                long_start = param.time
                                long_type = 'bigslide'
                                in_slide = True
                            case '7' | '9':
                                long_type = 'balloon'
                                long_start = param.time
                            case '8':
                                slide_length = round(slide_length)
                                match long_type:
                                    case 'slide':
                                        section[branch][1].append(
                                            formats['slide'].format(int(long_start), 256 + slide_length, slide_length))
                                    case 'bigslide':
                                        section[branch][1].append(
                                            formats['bigslide'].format(int(long_start), 256 + slide_length, slide_length))
                                    case 'balloon':
                                        end_time = param.time + param.time_per_char(char)
                                        section[branch][1].append(
                                            formats['spin'].format(int(long_start), int(end_time)))
                                slide_length = 0
                                in_slide = False
                            case ',':
                                measure.clear()
                                char = 0
                                break

                        param.time += param.time_per_char(char)
    return courses
                            
def dumps(courses):
    beatmaps = [[], [], [], [], []]
    for c, course in enumerate(courses):
        if not course:
            continue
        branches = [None, None, None]
        timings = [[], [], []]
        objects = [[], [], []]
        for section in course:
            for b in range(3):
                if len(course) == 1 and section[b] is None:
                    continue
                selected = b
                if section[b] is None:
                    selected = 0
                timings[b].extend(section[selected][0])
                objects[b].extend(section[selected][1])
        for b in range(3):
            if objects[b] == []:
                continue
            tmp = beatmap.format(
                metadata.wave,
                int(metadata.demostart * 1000),
                metadata.title,
                metadata.titlejp if metadata.titlejp else metadata.title,
                f'{course_name[c]} {branch_name[b]}'
            )
            tmp += '\n\n[TimingPoints]\n'
            tmp += '\n'.join(timings[b])
            tmp += '\n\n[HitObjects]\n'
            tmp += '\n'.join(objects[b])
            branches[b] = tmp
        beatmaps[c] = branches
    return beatmaps

def read_file(filename):
    encodings = ['utf-8-sig', 'shift-jis', 'utf-8']
    for encoding in encodings:
        try:
            with open(filename, 'r', encoding=encoding) as f:
                content = f.readlines()
                return content
        except UnicodeDecodeError:
            pass
    with open(filename, 'r', encoding='utf-8-sig', errors='ignore') as f:
        content = f.readlines()
        return content

def dump_maps(tja):
    print(f'{os.path.basename(tja):<60}', end='\r')
    folder = os.path.dirname(tja)
    content = read_file(tja)
    result = parse(content)
    beatmaps = dumps(result)
    for c, course in enumerate(beatmaps):
        # only export all branches of Oni and Inner Oni and master branch of other courses.
        if course == []:
            continue
        if c < 3:
            if course[2] is not None:
                course[0] = course[1] = None
            else:
                course[1] = course[2] = None
            
        for b, branch in enumerate(course):
            if branch is None:
                continue
            filename = f'{metadata.title} [{course_name[c]}] [{branch_name[b]}].osu'
            filename = re.sub(r'[<>:"/\\|?*]', '', filename)
            with open(os.path.join(folder, filename), 'w', encoding='utf8') as f:
                f.write(branch)


if __name__ == '__main__':
    convert_list = sys.argv[1:]
    # convert_list = [r"D:\game\taiko\maps\ESE\06 Classical"]
    for f in convert_list:
        if os.path.isdir(f):
            for root, dirs, files in os.walk(f):
                for file in files:
                    if file.endswith('.tja'):
                        try:
                            dump_maps(os.path.join(root, file))
                        except Exception as e:
                            print()
                            print(e)
        elif os.path.isfile(f):
            if f.endswith('.tja'):
                try:
                    dump_maps(f)
                except Exception as e:
                    print()
                    print(e)
    input('\nPress Enter to exit...')
                
                

