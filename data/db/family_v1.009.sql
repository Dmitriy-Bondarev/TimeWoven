PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE AvatarHistory (
    avatar_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id    INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    target_year  INTEGER,
    is_current   INTEGER NOT NULL DEFAULT 0,
    source_type  TEXT NOT NULL,
    created_at   TEXT,
    metadata     TEXT,
    FOREIGN KEY (person_id) REFERENCES People(person_id)
);
INSERT INTO AvatarHistory VALUES(1,1,'/static/avatars/person_1.jpg',NULL,0,'upload','2026-04-12 15:27:30',NULL);
INSERT INTO AvatarHistory VALUES(2,1,'/static/avatars/person_1.jpg',NULL,0,'upload','2026-04-12 15:27:44',NULL);
INSERT INTO AvatarHistory VALUES(3,1,'/static/avatars/person_1.png',NULL,0,'upload','2026-04-12 15:27:53',NULL);
INSERT INTO AvatarHistory VALUES(4,1,'/static/avatars/person_1.jpg',NULL,1,'upload','2026-04-12 15:28:09',NULL);
CREATE TABLE EventParticipants (
    event_id        INTEGER NOT NULL,
    person_id       INTEGER NOT NULL,
    participant_role TEXT NOT NULL,
    is_featured     INTEGER DEFAULT 0,
    added_at        TEXT,
    PRIMARY KEY (event_id, person_id, participant_role),
    FOREIGN KEY (event_id)  REFERENCES Events(event_id),
    FOREIGN KEY (person_id) REFERENCES People(person_id)
);
CREATE TABLE Events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id       INTEGER,
    location_id     INTEGER,
    event_type      TEXT NOT NULL,
    date_start      TEXT,
    date_start_prec TEXT,
    date_end        TEXT,
    date_end_prec   TEXT,
    is_private      INTEGER NOT NULL DEFAULT 0,
    cover_asset_id  INTEGER,
    FOREIGN KEY (author_id)   REFERENCES People(person_id),
    FOREIGN KEY (location_id) REFERENCES Places(place_id)
);
INSERT INTO Events VALUES(1,3,NULL,'wedding','1979-06-15','ABOUT',NULL,NULL,0,NULL);
INSERT INTO Events VALUES(2,3,NULL,'birth','1982-11-16','EXACT',NULL,NULL,0,NULL);
INSERT INTO Events VALUES(3,3,NULL,'birth','1977-09-28','EXACT',NULL,NULL,0,NULL);
INSERT INTO Events VALUES(4,3,NULL,'death','2005-02-09','EXACT',NULL,NULL,0,NULL);
INSERT INTO Events VALUES(5,3,NULL,'birth','2009-04-13','EXACT',NULL,NULL,0,NULL);
INSERT INTO Events VALUES(6,3,NULL,'memory_recording','2026-04-06','EXACT',NULL,NULL,0,NULL);
CREATE TABLE Memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER,
  event_id INTEGER,
  content_text TEXT,
  audio_url TEXT,
  transcript_verbatim TEXT,
  transcript_readable TEXT,
  emotional_tone TEXT,
  intimacy_level INTEGER DEFAULT 1,
  sensitivity_flag INTEGER DEFAULT 0,
  confidence_score REAL,
  created_at TEXT DEFAULT (datetime('now')),
  created_by INTEGER,
  source_type TEXT, parent_memory_id INTEGER REFERENCES Memories(id),
  FOREIGN KEY (author_id) REFERENCES People(person_id),
  FOREIGN KEY (event_id) REFERENCES Events(event_id),
  FOREIGN KEY (created_by) REFERENCES People(person_id)
);
INSERT INTO Memories VALUES(2,3,NULL,'Знаешь, Ванечка, тебе скоро будет 17 лет, а представь себе, что я к тебе обращаюсь, ну, к 37 летнему, значит, это будет через 30 лет. Какой ты станешь через 30 лет? Наверное, будешь важный, целеустремленный. Может быть, как папа такой же трудолюбивый, что тебя от нее не оттянешь. Важно скорее, интересно, закончил ли ты институт, поступил ли ты как хотел в престижный московский вуз, потому что хотеть этого мало, надо еще заниматься. В общем, я думаю, с твоей целеустремленностью у тебя все получилось, и ты уже важный специалист. Может быть, все-таки в историки пошел. Ведь ты очень любишь историю, географию, а это совсем не то же, что информатика. Очень интересно посмотреть, как же, что из тебя получилось, как ты определился в жизни. Но я думаю, что все нормально.','processed/13517383557209.mp3','Знаешь, Ванечка, тебе скоро будет 17 лет, а представь себе, что я к тебе обращаюсь, ну, к 37 летнему, значит, это будет через 30 лет. Какой ты станешь через 30 лет? Наверное, будешь важной, цельюстремленной. Может быть, как папа такой же трудолюбивый, что тебя от нет не отянешь на работу, на работу. Важно скорее, интересно, закончил ли ты институт, поступил ли ты как хотел в престижный московский вуз, потому что хотите этого мало, надо еще заниматься. В общем, я думаю, с твоей цельюстремленностью у тебя все получилось, и ты уже важный специалист. Может быть, все-таки в историке пошел. Ведь ты очень любишь историю, географию, а это совсем не то же, что информатика. Очень интересно посмотреть, как же, что из тебя получилось, как ты определился в жизни. Но я думаю, что все нормально.','Знаешь, Ванечка, тебе скоро будет 17 лет, а представь себе, что я к тебе обращаюсь, ну, к 37 летнему, значит, это будет через 30 лет. Какой ты станешь через 30 лет? Наверное, будешь важной, цельюстремленной. Может быть, как папа такой же трудолюбивый, что тебя от нет не отянешь на работу, на работу. Важно скорее, интересно, закончил ли ты институт, поступил ли ты как хотел в престижный московский вуз, потому что хотите этого мало, надо еще заниматься. В общем, я думаю, с твоей цельюстремленностью у тебя все получилось, и ты уже важный специалист. Может быть, все-таки в историке пошел. Ведь ты очень любишь историю, географию, а это совсем не то же, что информатика. Очень интересно посмотреть, как же, что из тебя получилось, как ты определился в жизни. Но я думаю, что все нормально.','неопределённый',1,0,0.949999999999999956,'2026-04-06T16:38:47',1,'voice_note',NULL);
INSERT INTO Memories VALUES(3,3,NULL,'А знаешь, для всех вообще-то мне очень интересно посмотреть, какие вы все будете через 30 лет. Потому что сейчас еще и Дима, и Леша полны сил, полны энергии, творческие какие-то замыслы. Мальчики и девочки еще не определились в жизни, пока еще учатся. Старшие учатся, старшие — это Марина и Дима. Кирилл и Яна еще не совсем никак не определились, катятся по жизни так, как колобочки. Хотя Яна более целеустремленная, чем Кирилл. Чего-то он завяз в своих играх. Он ничего не хочет видеть, слышать, кроме игр. Тоже так не бывает. Какой-то интерес в жизни все равно должен быть. На играх не проживешь.','processed/13517490577497.mp3','А знаешь, для всех вообще-то мне очень интересно посмотреть, какие вы все будете через 30 лет. Потому что сейчас еще и Дима, и Леша полны сил, полны энергии, творческие какие-то замыслы. Мальчики и девочки еще не определились в жизни, пока еще учатся. Старшие учатся, старшие — это Марина и Дима. Кирилл и Яна еще не совсем никак не определились, катятся по жизни так, как колобочки. Хотя Янга более целеустремленная, чем Кирилл. Чего-то он завяз в своих играх. Он ничего не хочет видеть, кроме слышать, кроме игр. Тоже так не бывает. Какой-то интерес в жизни все равно должен быть. На играх не проживешь.','А знаешь, для всех вообще-то мне очень интересно посмотреть, какие вы все будете через 30 лет. Потому что сейчас еще и Дима, и Леша полны сил, полны энергии, творческие какие-то замыслы. Мальчики и девочки еще не определились в жизни, пока еще учатся. Старшие учатся, старшие — это Марина и Дима. Кирилл и Яна еще не совсем никак не определились, катятся по жизни так, как колобочки. Хотя Янга более целеустремленная, чем Кирилл. Чего-то он завяз в своих играх. Он ничего не хочет видеть, кроме слышать, кроме игр. Тоже так не бывает. Какой-то интерес в жизни все равно должен быть. На играх не проживешь.','неопределённый',1,0,0.949999999999999956,'2026-04-06T16:38:52',1,'voice_note',NULL);
INSERT INTO Memories VALUES(4,3,NULL,'Наверное, нас жизнь не держит только... Я сейчас по себе, наверное, думаю, что мне не хочется бросать детей внуков, что мне хочется посмотреть, а как у них сложилось жизнь. Наверное, нас жизнь не держит только... Я сейчас по себе, наверное, думаю, что мне не хочется бросать детей внуков, что мне хочется посмотреть, а как у них сложилось жизнь. ','processed/13517499883609.mp3','Наверное, нас жизнь не держит только... Я сейчас по себе, наверное, думаю, что мне не хочется бросать детей внуков, что мне хочется посмотреть, а как у них сложилось жизнь. Повторяюсь, ладно.','Наверное, нас жизнь не держит только... Я сейчас по себе, наверное, думаю, что мне не хочется бросать детей внуков, что мне хочется посмотреть, а как у них сложилось жизнь. Повторяюсь, ладно.','неопределённый',1,0,0.949999999999999956,'2026-04-06T16:38:53',1,'voice_note',NULL);
CREATE TABLE MemoryPeople (
  memory_id INTEGER NOT NULL,
  person_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('author', 'mentioned', 'addressee', 'subject')),
  PRIMARY KEY (memory_id, person_id, role),
  FOREIGN KEY (memory_id) REFERENCES Memories(id),
  FOREIGN KEY (person_id) REFERENCES People(person_id)
);
INSERT INTO MemoryPeople VALUES(2,3,'author');
INSERT INTO MemoryPeople VALUES(2,6,'addressee');
INSERT INTO MemoryPeople VALUES(2,6,'subject');
INSERT INTO MemoryPeople VALUES(3,3,'author');
INSERT INTO MemoryPeople VALUES(3,1,'mentioned');
INSERT INTO MemoryPeople VALUES(3,2,'mentioned');
INSERT INTO MemoryPeople VALUES(3,7,'mentioned');
INSERT INTO MemoryPeople VALUES(3,8,'mentioned');
INSERT INTO MemoryPeople VALUES(3,9,'mentioned');
INSERT INTO MemoryPeople VALUES(4,3,'author');
INSERT INTO MemoryPeople VALUES(4,1,'subject');
INSERT INTO MemoryPeople VALUES(4,2,'subject');
INSERT INTO MemoryPeople VALUES(4,6,'subject');
INSERT INTO MemoryPeople VALUES(4,7,'subject');
INSERT INTO MemoryPeople VALUES(4,8,'subject');
INSERT INTO MemoryPeople VALUES(4,9,'subject');
CREATE TABLE People (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    maiden_name TEXT,
    gender TEXT CHECK (gender IN ('M', 'F', 'Unknown')),
    birth_date TEXT,
    birth_date_prec TEXT CHECK (birth_date_prec IN ('EXACT', 'ABOUT', 'YEARONLY', 'DECADE')),
    death_date TEXT,
    death_date_prec TEXT CHECK (death_date_prec IN ('EXACT', 'ABOUT', 'YEARONLY', 'DECADE')),
    is_alive INTEGER NOT NULL DEFAULT 1 CHECK (is_alive IN (0, 1)),
    is_user INTEGER NOT NULL DEFAULT 0 CHECK (is_user IN (0, 1)),
    role TEXT NOT NULL DEFAULT 'placeholder' CHECK (role IN ('admin', 'author', 'relative', 'placeholder')),
    successor_id INTEGER,
    default_lang TEXT NOT NULL DEFAULT 'ru',
    phone TEXT,
    preferred_ch TEXT CHECK (preferred_ch IN ('TG', 'Email', 'Push')),
    avatar_url TEXT, pin TEXT,
    FOREIGN KEY (successor_id) REFERENCES People(person_id)
);
INSERT INTO People VALUES(1,NULL,'M','1977-09-28','EXACT',NULL,NULL,1,1,'admin',NULL,'ru','+79856479911','TG','/static/avatars/person_1.jpg','1977');
INSERT INTO People VALUES(2,NULL,'M','1982-11-16','EXACT',NULL,NULL,1,0,'relative',NULL,'ru','+79181798188','Email','/static/avatars/person_2.webp','1982');
INSERT INTO People VALUES(3,'Дубейко','F','1956-03-26','EXACT',NULL,NULL,1,0,'relative',NULL,'ru','+79184544424','TG','/static/avatars/person_3.jpg','1956');
INSERT INTO People VALUES(4,'','M','1951-11-14','EXACT','2005-02-09','EXACT',0,0,'relative',NULL,'ru',NULL,NULL,'/static/avatars/person_4.jpeg','1951');
INSERT INTO People VALUES(5,NULL,'F','1982-02-19','EXACT',NULL,NULL,1,0,'relative',NULL,'ru','+79186373110','Email','/static/avatars/person_5.webp','1982');
INSERT INTO People VALUES(6,NULL,'M','2009-04-13','EXACT',NULL,NULL,1,0,'relative',NULL,'ru','+79182507546','TG','/static/avatars/person_6.webp','2009');
INSERT INTO People VALUES(7,NULL,'M','2012-10-11','EXACT',NULL,NULL,1,0,'relative',NULL,'ru','+79878300703','Push','/static/avatars/person_7.webp','2012');
INSERT INTO People VALUES(8,'Бондарева','F','2017-11-07','EXACT',NULL,NULL,1,0,'relative',NULL,'ru','+79184544408','Push','/static/avatars/person_8.webp','2017');
INSERT INTO People VALUES(9,'Бондарева','F','2005-04-01','EXACT',NULL,NULL,1,0,'admin',NULL,'ru','+79854767168','TG','/static/avatars/person_9.jpg','2005');
CREATE TABLE People_I18n (
    person_id   INTEGER NOT NULL,
    lang_code   TEXT    NOT NULL,
    first_name  TEXT    NOT NULL,
    last_name   TEXT,
    patronymic  TEXT,
    biography   TEXT,
    PRIMARY KEY (person_id, lang_code),
    FOREIGN KEY (person_id) REFERENCES People(person_id)
);
INSERT INTO People_I18n VALUES(1,'ru','Дмитрий','Бондарев','Александрович',NULL);
INSERT INTO People_I18n VALUES(1,'en','Dmitrii','Bondarev','Aleksandrovich',NULL);
INSERT INTO People_I18n VALUES(2,'ru','Алексей','Бондарев','Александрович',NULL);
INSERT INTO People_I18n VALUES(2,'en','Aleksei','Bondarev','Aleksandrovich',NULL);
INSERT INTO People_I18n VALUES(3,'ru','Наталия','Бондарева','Ивановна',NULL);
INSERT INTO People_I18n VALUES(3,'en','Natalia','Bondareva','Ivanovna',NULL);
INSERT INTO People_I18n VALUES(4,'ru','Александр','Бондарев','Михайлович',NULL);
INSERT INTO People_I18n VALUES(4,'en','Aleksandr','Bondarev','Mikhailovich',NULL);
INSERT INTO People_I18n VALUES(5,'ru','Елена','Бондарева',NULL,NULL);
INSERT INTO People_I18n VALUES(5,'en','Elena','Bondareva',NULL,NULL);
INSERT INTO People_I18n VALUES(6,'ru','Иван','Бондарев','Алексеевич',NULL);
INSERT INTO People_I18n VALUES(6,'en','Ivan','Bondarev','Alekseevich',NULL);
INSERT INTO People_I18n VALUES(7,'ru','Кирилл','Бондарев','Алексеевич',NULL);
INSERT INTO People_I18n VALUES(7,'en','Kirill','Bondarev','Alekseevich',NULL);
INSERT INTO People_I18n VALUES(8,'ru','Яна','Бондарева','Алексеевна',NULL);
INSERT INTO People_I18n VALUES(8,'en','Yana','Bondareva','Alekseevna',NULL);
INSERT INTO People_I18n VALUES(9,'ru','Марина','Зальбург','Дмитриевна','Помогает вести семейную базу.');
INSERT INTO People_I18n VALUES(9,'en','Marina','Zalburg','Dmitrievna',NULL);
CREATE TABLE PersonRelationship (
    rel_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    person_from_id     INTEGER NOT NULL,
    person_to_id       INTEGER NOT NULL,
    relationship_type_id INTEGER NOT NULL,
    is_primary         INTEGER NOT NULL DEFAULT 1,
    valid_from         TEXT,
    valid_to           TEXT,
    comment            TEXT,
    FOREIGN KEY (person_from_id) REFERENCES People(person_id),
    FOREIGN KEY (person_to_id)   REFERENCES People(person_id),
    FOREIGN KEY (relationship_type_id) REFERENCES RelationshipType(id)
);
INSERT INTO PersonRelationship VALUES(1,3,1,1,1,NULL,NULL,'мать->сын');
INSERT INTO PersonRelationship VALUES(2,3,2,1,1,NULL,NULL,'мать->сын');
INSERT INTO PersonRelationship VALUES(3,1,3,2,1,NULL,NULL,'сын->мать');
INSERT INTO PersonRelationship VALUES(4,2,3,2,1,NULL,NULL,'сын->мать');
INSERT INTO PersonRelationship VALUES(5,4,3,3,1,NULL,NULL,'супруг->супруга');
INSERT INTO PersonRelationship VALUES(6,3,4,3,1,NULL,NULL,'супруга->супруг');
INSERT INTO PersonRelationship VALUES(7,4,1,1,1,NULL,NULL,'отец->сын');
INSERT INTO PersonRelationship VALUES(8,1,4,2,1,NULL,NULL,'сын->отец');
INSERT INTO PersonRelationship VALUES(9,4,2,1,1,NULL,NULL,'отец->сын');
INSERT INTO PersonRelationship VALUES(10,2,4,2,1,NULL,NULL,'сын->отец');
INSERT INTO PersonRelationship VALUES(11,1,2,5,1,NULL,NULL,'брат->брат');
INSERT INTO PersonRelationship VALUES(12,2,1,5,1,NULL,NULL,'брат->брат');
INSERT INTO PersonRelationship VALUES(13,2,5,3,1,NULL,NULL,'Брат -> супруга, официальный брак');
INSERT INTO PersonRelationship VALUES(14,5,2,3,1,NULL,NULL,'Супруга -> брат, официальный брак');
INSERT INTO PersonRelationship VALUES(15,2,6,1,1,NULL,NULL,'Отец -> сын Иван');
INSERT INTO PersonRelationship VALUES(16,6,2,2,1,NULL,NULL,'Иван -> отец');
INSERT INTO PersonRelationship VALUES(17,5,6,1,1,NULL,NULL,'Мать -> сын Иван');
INSERT INTO PersonRelationship VALUES(18,6,5,2,1,NULL,NULL,'Иван -> мать');
INSERT INTO PersonRelationship VALUES(19,2,7,1,1,NULL,NULL,'Отец -> сын Кирилл');
INSERT INTO PersonRelationship VALUES(20,7,2,2,1,NULL,NULL,'Кирилл -> отец');
INSERT INTO PersonRelationship VALUES(21,5,7,1,1,NULL,NULL,'Мать -> сын Кирилл');
INSERT INTO PersonRelationship VALUES(22,7,5,2,1,NULL,NULL,'Кирилл -> мать');
INSERT INTO PersonRelationship VALUES(23,2,8,1,1,NULL,NULL,'Отец -> дочь Яна');
INSERT INTO PersonRelationship VALUES(24,8,2,2,1,NULL,NULL,'Яна -> отец');
INSERT INTO PersonRelationship VALUES(25,5,8,1,1,NULL,NULL,'Мать -> дочь Яна');
INSERT INTO PersonRelationship VALUES(26,8,5,2,1,NULL,NULL,'Яна -> мать');
INSERT INTO PersonRelationship VALUES(27,6,7,5,1,NULL,NULL,'Иван -> Кирилл, родные братья');
INSERT INTO PersonRelationship VALUES(28,7,6,5,1,NULL,NULL,'Кирилл -> Иван, родные братья');
INSERT INTO PersonRelationship VALUES(29,6,8,5,1,NULL,NULL,'Иван -> Яна, родные брат и сестра');
INSERT INTO PersonRelationship VALUES(30,8,6,5,1,NULL,NULL,'Яна -> Иван, родные сестра и брат');
INSERT INTO PersonRelationship VALUES(31,7,8,5,1,NULL,NULL,'Кирилл -> Яна, родные брат и сестра');
INSERT INTO PersonRelationship VALUES(32,8,7,5,1,NULL,NULL,'Яна -> Кирилл, родные сестра и брат');
INSERT INTO PersonRelationship VALUES(33,1,9,1,1,NULL,NULL,'Отец -> дочь Марина');
INSERT INTO PersonRelationship VALUES(34,9,1,2,1,NULL,NULL,'Марина -> отец');
INSERT INTO PersonRelationship VALUES(35,3,9,1,1,NULL,NULL,'Бабушка -> внучка Марина');
INSERT INTO PersonRelationship VALUES(36,9,3,2,1,NULL,NULL,'Марина -> бабушка');
INSERT INTO PersonRelationship VALUES(37,4,9,1,1,NULL,NULL,'Дедушка -> внучка Марина');
INSERT INTO PersonRelationship VALUES(38,9,4,2,1,NULL,NULL,'Марина -> дедушка');
INSERT INTO PersonRelationship VALUES(39,3,6,1,1,NULL,NULL,'Бабушка -> внук Иван');
INSERT INTO PersonRelationship VALUES(40,6,3,2,1,NULL,NULL,'Иван -> бабушка');
INSERT INTO PersonRelationship VALUES(41,3,7,1,1,NULL,NULL,'Бабушка -> внук Кирилл');
INSERT INTO PersonRelationship VALUES(42,7,3,2,1,NULL,NULL,'Кирилл -> бабушка');
INSERT INTO PersonRelationship VALUES(43,3,8,1,1,NULL,NULL,'Бабушка -> внучка Яна');
INSERT INTO PersonRelationship VALUES(44,8,3,2,1,NULL,NULL,'Яна -> бабушка');
INSERT INTO PersonRelationship VALUES(45,4,6,1,1,NULL,NULL,'Дедушка -> внук Иван');
INSERT INTO PersonRelationship VALUES(46,6,4,2,1,NULL,NULL,'Иван -> дедушка');
INSERT INTO PersonRelationship VALUES(47,4,7,1,1,NULL,NULL,'Дедушка -> внук Кирилл');
INSERT INTO PersonRelationship VALUES(48,7,4,2,1,NULL,NULL,'Кирилл -> дедушка');
INSERT INTO PersonRelationship VALUES(49,4,8,1,1,NULL,NULL,'Дедушка -> внучка Яна');
INSERT INTO PersonRelationship VALUES(50,8,4,2,1,NULL,NULL,'Яна -> дедушка');
CREATE TABLE Places (
    place_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    country     TEXT,
    region      TEXT,
    city        TEXT,
    coordinates TEXT,
    address_raw TEXT,
    metadata    TEXT
);
CREATE TABLE Quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  content_text TEXT NOT NULL,
  source_memory_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (author_id) REFERENCES People(person_id),
  FOREIGN KEY (source_memory_id) REFERENCES Memories(id)
);
INSERT INTO Quotes VALUES(1,3,'Хотеть этого мало, надо еще заниматься.',2,'2026-04-09 09:50:24');
INSERT INTO Quotes VALUES(2,3,'Какой-то интерес в жизни все равно должен быть. На играх не проживешь.',3,'2026-04-09 09:50:24');
INSERT INTO Quotes VALUES(3,3,'Мне хочется посмотреть, а как у них сложилась жизнь.',4,'2026-04-09 09:50:24');
CREATE TABLE RelationshipType (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL,
    symmetry_type  TEXT NOT NULL,
    category       TEXT NOT NULL,
    inverse_type_id INTEGER,
    FOREIGN KEY (inverse_type_id) REFERENCES RelationshipType(id)
);
INSERT INTO RelationshipType VALUES(1,'bioparent','Inverse','blood',2);
INSERT INTO RelationshipType VALUES(2,'child','Inverse','blood',1);
INSERT INTO RelationshipType VALUES(3,'spouselegal','Symmetrical','legal',3);
INSERT INTO RelationshipType VALUES(4,'spousecommon','Symmetrical','social',4);
INSERT INTO RelationshipType VALUES(5,'siblingfull','Symmetrical','blood',5);
INSERT INTO RelationshipType VALUES(6,'siblinghalf','Symmetrical','blood',6);
INSERT INTO RelationshipType VALUES(7,'adoptparent','Inverse','legal',8);
INSERT INTO RelationshipType VALUES(8,'adoptchild','Inverse','legal',7);
INSERT INTO RelationshipType VALUES(9,'stepparent','Inverse','social',10);
INSERT INTO RelationshipType VALUES(10,'stepchild','Inverse','social',9);
INSERT INTO RelationshipType VALUES(11,'guardian','Inverse','legal',12);
INSERT INTO RelationshipType VALUES(12,'ward','Inverse','legal',11);
INSERT INTO sqlite_sequence VALUES('Memories',20);
INSERT INTO sqlite_sequence VALUES('People',9);
INSERT INTO sqlite_sequence VALUES('PersonRelationship',50);
INSERT INTO sqlite_sequence VALUES('Quotes',3);
INSERT INTO sqlite_sequence VALUES('RelationshipType',12);
INSERT INTO sqlite_sequence VALUES('AvatarHistory',4);
INSERT INTO sqlite_sequence VALUES('Events',6);
COMMIT;
