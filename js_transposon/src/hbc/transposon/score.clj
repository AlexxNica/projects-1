;; Assess reliability of merged insertions sites by normalizing and
;; assigning quality scores.

(ns hbc.transposon.score
  (:use [incanter.io :only [read-dataset]])
  (:require [incanter.core :as icore]
            [incanter.stats :as stats]
            [clojure.string :as string]
            [fs]))

;; Columns that are not experimental data
(def ^:dynamic *ignore-cols* #{:chr :pos :seq})

;; ## Dataset statistics

(defn summarize-count-statistics [ds]
  "Summarize statistics of counts in each experiment."
  (letfn [(exp-stats [xs]
            [(stats/mean xs) (stats/median xs) (stats/sd xs)])]
    (map #(cons % (exp-stats (icore/sel ds :cols %)))
         (remove #(contains? *ignore-cols* %) (icore/col-names ds)))))

(defn print-count-stats [ds]
  "Print out count statistics for the given dataset"
  (println ("exp | mean | median | std-dev"))
  (doseq [[x m md sd] (summarize-count-statistics ds)]
    (println (format "%s | %.1f | %.1f | %.2f" x m md sd)))
  ds)

;; ## Dataset normalization
;;
;; Normalize columns by total reads and rows by percentage of maximum
;; to allow experiment and position comparisons.

(defn normalize-counts
  "Normalize counts to standard metric based on totals in each experiment.
   By default normalizes to total count in a column scaled to 1 million reads."
  [dataset & {:keys [base ignore]
              :or {base 1e6
                   ignore *ignore-cols*}}]
  (letfn [(normalize [x total]
            (* (/ x total) base))
          (maybe-normalize [ds col]
            (if-not (contains? ignore col)
              (icore/transform-col ds col normalize
                                   (float (apply + (icore/sel ds :cols col))))
              ds))]
    (loop [ds dataset
           cols (icore/col-names ds)]
      (if-let [col (first cols)]
        (recur (maybe-normalize ds col) (rest cols))
        ds))))

(defn- process-row [ds row f ignore]
  "Process columns of interest in the current row"
  (let [[same-cols proc-cols] ((juxt filter remove) #(contains? ignore %) (icore/col-names ds))]
    (merge
     (zipmap same-cols (map #(icore/sel ds :rows row :cols %) same-cols))
     (zipmap proc-cols (f (map #(icore/sel ds :rows row :cols %) proc-cols))))))

(defn normalize-pos-ratios
  "Normalize counts as the percentage of the max at a position.
   This normalizes by row, in contrast to normalize-counts
   which handles columns."
  [ds & {:keys [ignore]
              :or {ignore *ignore-cols*}}]
  (letfn [(normalize-row [row]
            (let [cur-max (apply max row)]
              (map #(/ % cur-max) row)))]
    (icore/dataset (icore/col-names ds)
                   (map #(process-row ds % normalize-row ignore)
                        (range (icore/nrow ds))))))

; ## Top level functionality

(defn normalize-merge [merge-file]
  "Normalize and prepare statistics on a merged file."
  (-> (read-dataset merge-file :header true)
      normalize-counts
      normalize-pos-ratios
      print-count-stats
      icore/save (format "%s-normal.csv" (-> merge-file (string/split #"\.") first))))

(defn -main [merge-file]
  (normalize-merge merge-file))
